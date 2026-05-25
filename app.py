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

        # Mapa: horário → candidatos disponíveis
        disponivel_em = {
            h: [n for n, d in diretores.items() if h in d["disponibilidade"]]
            for h in todos_horarios
        }

        # Ordena horários do mais escasso ao mais abundante (fixo)
        horarios_ordenados = sorted(
            todos_horarios,
            key=lambda h: len(disponivel_em[h])
        )

        # Contagem de plantões mutável durante o backtracking
        plantoes = {nome: 0 for nome in diretores}

        def backtrack(idx):
            """
            Tenta preencher horarios_ordenados[idx:] usando backtracking.
            Retorna True se encontrou solução completa, False se não há saída.
            """
            # Pula horários sem nenhum disponível (impossíveis de preencher)
            while idx < len(horarios_ordenados) and len(disponivel_em[horarios_ordenados[idx]]) == 0:
                idx += 1

            if idx == len(horarios_ordenados):
                return True  # todos os horários tratados

            horario = horarios_ordenados[idx]

            # Candidatos: disponíveis nesse horário com < 2 plantões
            candidatos = [
                n for n in disponivel_em[horario]
                if plantoes[n] < 2
            ]

            if not candidatos:
                return False  # beco sem saída → backtrack

            # Prioriza quem tem menos disponibilidades totais (mais "raro") e depois
            # quem já tem menos plantões — garante que ninguém com 1 slot fique de fora
            candidatos.sort(key=lambda n: (
                plantoes[n],
                len(diretores[n]["disponibilidade"])
            ))
            # Shuffle leve dentro de candidatos com mesmo score para variar a escala
            grupos = {}
            for n in candidatos:
                k = (plantoes[n], len(diretores[n]["disponibilidade"]))
                grupos.setdefault(k, []).append(n)
            for g in grupos.values():
                random.shuffle(g)
            candidatos = [n for k in sorted(grupos) for n in grupos[k]]

            for escolhido in candidatos:
                alocacao[horario].append(escolhido)
                plantoes[escolhido] += 1

                if backtrack(idx + 1):
                    return True  # solução encontrada, propaga

                # Desfaz e tenta o próximo candidato
                alocacao[horario].remove(escolhido)
                plantoes[escolhido] -= 1

            return False  # nenhum candidato funcionou

        with st.status("⚙️ Gerando escala...", expanded=True) as status:
            st.write("🔍 Analisando disponibilidades...")
            total = len([h for h in horarios_ordenados if len(disponivel_em[h]) > 0])

            progresso = st.progress(0, text="Iniciando alocação...")
            contador = [0]

            _backtrack_original = backtrack

            def backtrack_com_progresso(idx):
                while idx < len(horarios_ordenados) and len(disponivel_em[horarios_ordenados[idx]]) == 0:
                    idx += 1
                if idx == len(horarios_ordenados):
                    return True

                horario = horarios_ordenados[idx]
                candidatos = [n for n in disponivel_em[horario] if plantoes[n] < 2]
                if not candidatos:
                    return False

                candidatos.sort(key=lambda n: (plantoes[n], len(diretores[n]["disponibilidade"])))
                grupos = {}
                for n in candidatos:
                    k = (plantoes[n], len(diretores[n]["disponibilidade"]))
                    grupos.setdefault(k, []).append(n)
                for g in grupos.values():
                    random.shuffle(g)
                candidatos = [n for k in sorted(grupos) for n in grupos[k]]

                for escolhido in candidatos:
                    alocacao[horario].append(escolhido)
                    plantoes[escolhido] += 1

                    contador[0] += 1
                    pct = min(int((contador[0] / max(total, 1)) * 100), 99)
                    progresso.progress(pct, text=f"Alocando horários... ({pct}%)")

                    if backtrack_com_progresso(idx + 1):
                        return True

                    alocacao[horario].remove(escolhido)
                    plantoes[escolhido] -= 1

                return False

            st.write("📅 Executando alocação com backtracking...")
            backtrack_com_progresso(0)
            progresso.progress(100, text="Concluído!")
            status.update(label="✅ Escala gerada!", state="complete", expanded=False)

        # Copia plantões finais de volta para a estrutura original
        for nome in diretores:
            diretores[nome]["plantoes"] = plantoes[nome]

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

        for h in horarios_ordenados:
            if not alocacao[h]:
                if not disponivel_em[h]:
                    alertas.append(f"🚫 {h.replace('_', ' ')}: nenhum diretor marcou disponibilidade.")
                else:
                    nomes = ", ".join(disponivel_em[h])
                    alertas.append(
                        f"🚫 {h.replace('_', ' ')}: ficou vazio — "
                        f"todos os disponíveis ({nomes}) já têm 2 plantões."
                    )

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
