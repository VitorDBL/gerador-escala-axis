import streamlit as st
import pandas as pd
import random
import os
from PIL import Image
from io import BytesIO

st.set_page_config(layout="wide", page_title="Escala AXIS")

# ===============================
# LOGO
# ===============================
logo_path = "axis-sem-circulo_Branco.png"

if os.path.exists(logo_path):
    logo = Image.open(logo_path)
    col1, col2 = st.columns([1, 6])
    with col1:
        st.image(logo, width=120)
    with col2:
        st.markdown("## 📅 Gerador de Escala de Plantões – AXIS")
else:
    st.title("📅 Gerador de Escala de Plantões – AXIS")

uploaded_file = st.file_uploader("Selecione o CSV do Forms", type=["csv"])

if uploaded_file:

    df = pd.read_csv(uploaded_file, encoding="utf-8", sep=",", engine="python")
    df.columns = df.columns.str.strip()

    dias_col   = ["Segunda feira:", "Terça feira:", "Quarta feira:", "Quinta feira:", "Sexta feira:"]
    dias_curto = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira"]

    horas = [
        "12h-13h", "13h-14h", "14h-15h",
        "15h-16h", "16h-17h", "17h-18h",
        "18h-19h", "19h-20h", "20h-21h"
    ]

    todos_horarios = [
        f"{dia}_{h}"
        for dia in dias_curto
        for h in horas
    ]

    # ===============================
    # PARSE DA DISPONIBILIDADE
    # ===============================
    diretores = {}

    for _, row in df.iterrows():
        nome = str(row.iloc[1]).strip()
        disponibilidade = []

        for i, col in enumerate(dias_col):
            valor = str(row[col]).strip().lower()

            if valor in ("não posso", "nan", ""):
                continue

            horarios = [h.strip().strip('"') for h in valor.split(";") if h.strip()]

            for h in horarios:
                chave = f"{dias_curto[i]}_{h}"
                if chave in todos_horarios:
                    disponibilidade.append(chave)

        diretores[nome] = {
            "disponibilidade": list(set(disponibilidade)),
            "plantoes": 0
        }

    # ===============================
    # BOTÃO GERAR
    # ===============================
    if st.button("🔁 Gerar Nova Escala"):

        # RESET
        for nome in diretores:
            diretores[nome]["plantoes"] = 0

        alocacao = {h: [] for h in todos_horarios}
        alertas = []

        # Mapa: horário → lista de quem pode ficar nele
        disponivel_em = {
            h: [n for n, d in diretores.items() if h in d["disponibilidade"]]
            for h in todos_horarios
        }

        # Ordena todos os horários do mais escasso ao mais abundante (usado em todas as fases)
        horarios_por_escassez = sorted(
            todos_horarios,
            key=lambda h: len(disponivel_em[h])
        )

        # ============================================================
        # FASE 1A — Percorre horários do mais escasso ao mais abundante.
        # Para cada horário ainda vazio, aloca o candidato disponível
        # que ainda não tem plantão e tem MENOS disponibilidade total
        # (mais difícil de encaixar depois). Limite: 2 plantões.
        # ============================================================
        for horario in horarios_por_escassez:
            if len(alocacao[horario]) >= 1:
                continue

            # Só candidatos sem plantão ainda
            candidatos = [
                n for n in disponivel_em[horario]
                if diretores[n]["plantoes"] == 0
            ]

            if not candidatos:
                continue

            # Prefere quem tem menos disponibilidade total
            escolhido = min(candidatos, key=lambda n: len(diretores[n]["disponibilidade"]))
            alocacao[horario].append(escolhido)
            diretores[escolhido]["plantoes"] += 1

        # ============================================================
        # FASE 1B — Quem ainda não tem plantão (seus horários eram
        # todos escassos e foram preenchidos por outros na 1A).
        # Aloca no horário mais escasso disponível para ela, respeitando
        # limite de 2 e sem duplicar a pessoa no mesmo horário.
        # ============================================================
        diretores_sem = [
            n for n, d in diretores.items()
            if d["plantoes"] == 0 and len(d["disponibilidade"]) > 0
        ]
        # Ordena por menor disponibilidade (mais difíceis primeiro)
        diretores_sem.sort(key=lambda n: len(diretores[n]["disponibilidade"]))

        for nome in diretores_sem:
            horarios_candidatos = sorted(
                diretores[nome]["disponibilidade"],
                key=lambda h: len(disponivel_em[h])
            )
            for h in horarios_candidatos:
                if nome not in alocacao[h] and diretores[nome]["plantoes"] < 2:
                    alocacao[h].append(nome)
                    diretores[nome]["plantoes"] += 1
                    alertas.append(
                        f"⚠️ {nome} alocado em {h.replace('_', ' ')} "
                        f"(horário já ocupado — necessário para garantir 1 plantão)."
                    )
                    break

        # ============================================================
        # FASE 2 — Preencher horários ainda vazios com 2º plantão.
        # Percorre do mais escasso ao mais abundante.
        # Candidatos: disponíveis nesse horário com < 2 plantões.
        # Desempate: quem tem menos plantões; entre empatados, sorteia.
        # Limite absoluto: 2 plantões por pessoa, sem exceção.
        # ============================================================
        for horario in horarios_por_escassez:
            if len(alocacao[horario]) >= 1:
                continue

            candidatos = [
                n for n in disponivel_em[horario]
                if diretores[n]["plantoes"] < 2 and n not in alocacao[horario]
            ]

            if not candidatos:
                continue

            menor_qtd = min(diretores[n]["plantoes"] for n in candidatos)
            empatados = [n for n in candidatos if diretores[n]["plantoes"] == menor_qtd]
            escolhido = random.choice(empatados)

            alocacao[horario].append(escolhido)
            diretores[escolhido]["plantoes"] += 1

        # ============================================================
        # FASE 3 — Alertar horários que ficaram vazios.
        # Ninguém recebe mais de 2 plantões em nenhuma hipótese.
        # ============================================================
        for horario in horarios_por_escassez:
            if len(alocacao[horario]) >= 1:
                continue

            candidatos_disponiveis = disponivel_em[horario]

            if not candidatos_disponiveis:
                alertas.append(
                    f"🚫 {horario.replace('_', ' ')}: nenhum diretor marcou disponibilidade."
                )
            else:
                nomes = ", ".join(candidatos_disponiveis)
                alertas.append(
                    f"🚫 {horario.replace('_', ' ')}: ficou vazio — "
                    f"todos os disponíveis ({nomes}) já têm 2 plantões."
                )

        # ============================================================
        # ALERTAS FINAIS
        # ============================================================
        sem_disponibilidade = [
            n for n, d in diretores.items()
            if len(d["disponibilidade"]) == 0
        ]

        sem_plantao = [
            n for n, d in diretores.items()
            if d["plantoes"] == 0 and len(d["disponibilidade"]) > 0
        ]

        acima_limite = [
            n for n, d in diretores.items()
            if d["plantoes"] > 2
        ]

        # ============================================================
        # MONTAR TABELA
        # ============================================================
        tabela = []
        for h in horas:
            linha = [h]
            for dia in dias_curto:
                chave = f"{dia}_{h}"
                nomes = ", ".join(alocacao[chave]) if alocacao[chave] else "—"
                linha.append(nomes)
            tabela.append(linha)

        colunas = ["Horário"] + dias_curto
        df_final = pd.DataFrame(tabela, columns=colunas)

        st.subheader("📊 Escala Gerada")
        st.dataframe(df_final, use_container_width=True)

        # ============================================================
        # ESTATÍSTICAS
        # ============================================================
        stats = pd.DataFrame([
            {
                "Diretor": n,
                "Plantões": d["plantoes"],
                "Disponibilidades": len(d["disponibilidade"])
            }
            for n, d in diretores.items()
        ]).sort_values("Plantões", ascending=False)

        st.subheader("📈 Estatísticas")
        st.dataframe(stats, use_container_width=True)

        # ============================================================
        # EXIBIR ALERTAS
        # ============================================================
        if acima_limite:
            st.error("🚨 BUG: diretores com mais de 2 plantões (não deveria acontecer): " + ", ".join(acima_limite))

        if sem_disponibilidade:
            st.error("🚫 Sem disponibilidade alguma (não receberão plantão): " + ", ".join(sem_disponibilidade))

        if sem_plantao:
            st.error("🚨 Com disponibilidade mas sem plantão: " + ", ".join(sem_plantao))

        if alertas:
            st.warning("⚠️ Avisos da geração:")
            for a in alertas:
                st.write("-", a)

        if not sem_disponibilidade and not sem_plantao and not alertas and not acima_limite:
            st.success("✅ Escala gerada sem conflitos!")

        # ============================================================
        # DOWNLOAD EXCEL
        # ============================================================
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.to_excel(writer, index=False, sheet_name="Escala")
            stats.to_excel(writer, index=False, sheet_name="Estatísticas")

        st.download_button(
            label="⬇️ Baixar Escala em Excel",
            data=output.getvalue(),
            file_name="escala_axis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
