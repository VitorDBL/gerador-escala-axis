import streamlit as st
import pandas as pd
import random
import os
from PIL import Image
from io import BytesIO

st.set_page_config(layout="wide")

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

    dias = ["Segunda feira:", "Terça feira:", "Quarta feira:", "Quinta feira:", "Sexta feira:"]
    dias_curto = ["segunda-feira","terça-feira","quarta-feira","quinta-feira","sexta-feira"]

    diretores = {}

    for _, row in df.iterrows():
        nome = row.iloc[1]
        disponibilidade = []

        for i, dia in enumerate(dias):
            valor = str(row[dia]).strip().lower()

            if valor != "não posso" and valor != "nan":
                horarios = valor.split(",")

                for h in horarios:
                    h = h.strip().replace('"','')
                    disponibilidade.append(f"{dias_curto[i]}_{h}")

        diretores[nome] = {
            "disponibilidade": disponibilidade,
            "plantoes": 0
        }

    horas = [
        "12h-13h","13h-14h","14h-15h",
        "15h-16h","16h-17h","17h-18h",
        "18h-19h","19h-20h","20h-21"
    ]

    todos_horarios = [
        f"{dia}_{h}"
        for dia in dias_curto
        for h in horas
    ]

    if st.button("🔁 Gerar Nova Escala"):

        # RESET
        for nome in diretores:
            diretores[nome]["plantoes"] = 0

        alocacao = {h: [] for h in todos_horarios}
        conflitos = []

        # ==========================================
        # MAPEAR DISPONIBILIDADE POR HORÁRIO
        # ==========================================
        disponibilidade_por_horario = {
            h: [
                nome for nome, dados in diretores.items()
                if h in dados["disponibilidade"]
            ]
            for h in todos_horarios
        }

        # ==========================================
        # 1️⃣ GARANTIR PELO MENOS 1 PLANTÃO
        # PRIORIDADE: MENOR DISPONIBILIDADE
        # ==========================================
        diretores_ordenados = sorted(
            diretores.items(),
            key=lambda x: len(x[1]["disponibilidade"])
        )

        for nome, dados in diretores_ordenados:

            if not dados["disponibilidade"]:
                continue

            livres = [
                h for h in dados["disponibilidade"]
                if len(alocacao[h]) == 0
            ]

            if livres:
                escolhido = random.choice(livres)
            else:
                escolhido = random.choice(dados["disponibilidade"])
                conflitos.append(
                    f"{nome} foi alocado em {escolhido.replace('_',' ')} "
                    "porque era o único horário disponível para ele."
                )

            alocacao[escolhido].append(nome)
            diretores[nome]["plantoes"] += 1

        # ==========================================
        # 2️⃣ PRIORIZAR HORÁRIOS CRÍTICOS
        # ==========================================
        horarios_ordenados = sorted(
            todos_horarios,
            key=lambda h: len(disponibilidade_por_horario[h])
        )

        for horario in horarios_ordenados:

            if len(alocacao[horario]) >= 1:
                continue

            candidatos = [
                nome for nome in disponibilidade_por_horario[horario]
                if diretores[nome]["plantoes"] < 2
            ]

            if not candidatos:
                continue

            menor = min(diretores[n]["plantoes"] for n in candidatos)

            empatados = [
                n for n in candidatos
                if diretores[n]["plantoes"] == menor
            ]

            escolhido = random.choice(empatados)

            alocacao[horario].append(escolhido)
            diretores[escolhido]["plantoes"] += 1

        # ==========================================
        # ALERTAS DE QUEM FICOU SEM PLANTÃO
        # ==========================================

        sem_disponibilidade = [
            nome for nome, dados in diretores.items()
            if len(dados["disponibilidade"]) == 0
        ]

        sem_plantoes = [
            nome for nome, dados in diretores.items()
            if dados["plantoes"] == 0 and len(dados["disponibilidade"]) > 0
        ]

        if sem_plantoes:
            conflitos.append(
                "Alguns diretores não conseguiram plantão "
                "porque todos os horários possíveis já estavam ocupados."
            )

        # ==========================================
        # MONTAR TABELA
        # ==========================================
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

        # ==========================================
        # ESTATÍSTICAS
        # ==========================================
        stats = pd.DataFrame([
            {"Diretor": nome, "Plantões": dados["plantoes"]}
            for nome, dados in diretores.items()
        ]).sort_values("Plantões", ascending=False)

        st.subheader("📈 Estatísticas")
        st.dataframe(stats, use_container_width=True)

        # ==========================================
        # EXIBIR ALERTAS
        # ==========================================

        if sem_disponibilidade:
            st.error(
                "🚫 Os seguintes diretores marcaram 'não posso' em todos os horários e não poderão receber plantão: "
                + ", ".join(sem_disponibilidade)
            )

        if conflitos:
            st.warning("⚠️ Ajustes automáticos realizados:")
            for c in conflitos:
                st.write("-", c)

        if sem_plantoes:
            st.error(
                "🚨 Diretores com disponibilidade mas sem plantão: "
                + ", ".join(sem_plantoes)
            )

        # ==========================================
        # DOWNLOAD EXCEL
        # ==========================================
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Escala')
            stats.to_excel(writer, index=False, sheet_name='Estatisticas')

        st.download_button(
            label="⬇️ Baixar Escala em Excel",
            data=output.getvalue(),
            file_name="escala_axis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.success("Escala gerada com sucesso!")
