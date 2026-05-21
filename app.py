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

    # Colunas dos dias no CSV (novo formato)
    dias_col  = ["Segunda feira:", "Terça feira:", "Quarta feira:", "Quinta feira:", "Sexta feira:"]
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
    # Novo CSV usa ";" como separador
    # ===============================
    diretores = {}

    for _, row in df.iterrows():
        nome = str(row.iloc[1]).strip()
        disponibilidade = []

        for i, col in enumerate(dias_col):
            valor = str(row[col]).strip().lower()

            if valor in ("não posso", "nan", ""):
                continue

            # Novo formato: horários separados por ";"
            horarios = [h.strip().strip('"') for h in valor.split(";") if h.strip()]

            for h in horarios:
                chave = f"{dias_curto[i]}_{h}"
                if chave in todos_horarios:
                    disponibilidade.append(chave)

        diretores[nome] = {
            "disponibilidade": list(set(disponibilidade)),  # sem duplicatas
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

        # Mapa: horário → quem pode ficar nele
        disponivel_em = {
            h: [n for n, d in diretores.items() if h in d["disponibilidade"]]
            for h in todos_horarios
        }

        # ============================================================
        # FASE 1 — Garantir pelo menos 1 plantão por pessoa
        # Ordem: menor disponibilidade primeiro (mais difíceis de alocar)
        # Dentro de cada pessoa: priorizar o horário com MENOS opções
        # ============================================================
        diretores_ordenados = sorted(
            diretores.keys(),
            key=lambda n: len(diretores[n]["disponibilidade"])
        )

        for nome in diretores_ordenados:
            disponiveis = diretores[nome]["disponibilidade"]

            if not disponiveis:
                continue

            # Ordena os horários disponíveis do mais escasso ao mais abundante
            horarios_priorizados = sorted(
                disponiveis,
                key=lambda h: len(disponivel_em[h])
            )

            # Tenta horário sem ninguém ainda; se não tiver, pega o mais escasso
            alocado = False
            for h in horarios_priorizados:
                if len(alocacao[h]) == 0:
                    alocacao[h].append(nome)
                    diretores[nome]["plantoes"] += 1
                    alocado = True
                    break

            if not alocado:
                # Todos seus horários já têm alguém → pega o mais escasso que ainda não o tem
                for h in horarios_priorizados:
                    if nome not in alocacao[h] and diretores[nome]["plantoes"] < 2:
                        alocacao[h].append(nome)
                        diretores[nome]["plantoes"] += 1
                        alertas.append(
                            f"⚠️ {nome} foi alocado em {h.replace('_', ' ')} "
                            f"(horário já ocupado por outro — único disponível para garantir 1 plantão)."
                        )
                        break

        # ============================================================
        # FASE 2 — Preencher horários ainda vazios
        # Ordem: horários com MENOS disponíveis primeiro
        # Candidatos: quem pode e ainda tem < 2 plantões
        # Desempate: quem tem menos plantões → escolha aleatória
        # ============================================================
        horarios_por_escassez = sorted(
            todos_horarios,
            key=lambda h: len(disponivel_em[h])
        )

        for horario in horarios_por_escassez:
            if len(alocacao[horario]) >= 1:
                continue  # já preenchido

            candidatos = [
                n for n in disponivel_em[horario]
                if diretores[n]["plantoes"] < 2
            ]

            if not candidatos:
                continue  # Todos já têm 2 plantões ou ninguém disponível → alerta na fase 3

            # Prefere quem tem menos plantões; entre empatados, sorteia
            menor_qtd = min(diretores[n]["plantoes"] for n in candidatos)
            empatados = [n for n in candidatos if diretores[n]["plantoes"] == menor_qtd]
            escolhido = random.choice(empatados)

            alocacao[horario].append(escolhido)
            diretores[escolhido]["plantoes"] += 1

        # ============================================================
        # FASE 3 — Alertar horários que ficaram vazios
        # Ninguém será alocado além de 2 plantões
        # ============================================================
        for horario in horarios_por_escassez:
            if len(alocacao[horario]) >= 1:
                continue

            candidatos_disponiveis = disponivel_em[horario]

            if not candidatos_disponiveis:
                alertas.append(
                    f"🚫 Horário {horario.replace('_', ' ')} ficou vazio: "
                    f"nenhum diretor marcou disponibilidade para ele."
                )
            else:
                nomes = ", ".join(candidatos_disponiveis)
                alertas.append(
                    f"🚫 Horário {horario.replace('_', ' ')} ficou vazio: "
                    f"todos os diretores disponíveis ({nomes}) já atingiram o limite de 2 plantões."
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
            {"Diretor": n, "Plantões": d["plantoes"], "Disponibilidades": len(d["disponibilidade"])}
            for n, d in diretores.items()
        ]).sort_values("Plantões", ascending=False)

        st.subheader("📈 Estatísticas")
        st.dataframe(stats, use_container_width=True)

        # ============================================================
        # EXIBIR ALERTAS
        # ============================================================
        if sem_disponibilidade:
            st.error(
                "🚫 Sem disponibilidade alguma (não receberão plantão): "
                + ", ".join(sem_disponibilidade)
            )

        if sem_plantao:
            st.error(
                "🚨 Tinham disponibilidade mas ficaram sem plantão: "
                + ", ".join(sem_plantao)
                + " — verifique se havia conflitos."
            )

        if alertas:
            st.warning("⚠️ Ajustes realizados durante a geração:")
            for a in alertas:
                st.write("-", a)

        if not sem_disponibilidade and not sem_plantao and not alertas:
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
