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
        disponibilidade = set()

        for i, col in enumerate(dias_col):
            valor = str(row[col]).strip().lower()
            if valor in ("não posso", "nan", ""):
                continue
            for h in valor.split(";"):
                chave = f"{dias_curto[i]}_{h.strip().strip(chr(34))}"
                if chave in todos_horarios:
                    disponibilidade.add(chave)

        diretores[nome] = {
            "disponibilidade": disponibilidade,   # agora é set → lookup O(1)
            "plantoes": 0
        }

    # ===============================
    # BOTÃO GERAR
    # ===============================
    if st.button("🔁 Gerar Nova Escala"):

        for nome in diretores:
            diretores[nome]["plantoes"] = 0

        # Mapa: horário → lista de índices de diretores disponíveis
        nomes      = list(diretores.keys())          # índice estável
        disp_set   = [diretores[n]["disponibilidade"] for n in nomes]
        n_disp     = [len(d) for d in disp_set]      # total de disponibilidades por pessoa

        disponivel_em = {
            h: [i for i, d in enumerate(disp_set) if h in d]
            for h in todos_horarios
        }

        # Ordena horários: mais escassos primeiro (MRV heuristic)
        horarios_ordenados = sorted(
            todos_horarios,
            key=lambda h: len(disponivel_em[h])
        )
        # Filtra impossíveis logo de cara
        horarios_validos = [h for h in horarios_ordenados if disponivel_em[h]]

        plantoes   = [0] * len(nomes)       # int array → acesso O(1)
        alocacao   = {h: -1 for h in todos_horarios}   # -1 = vazio

        # ============================================================
        # BACKTRACKING ITERATIVO — sem recursão, sem list.remove()
        # ============================================================
        with st.spinner("⚙️ Gerando escala, aguarde..."):

            N      = len(horarios_validos)
            stack  = [0] * N          # stack[i] = próximo candidato a tentar no passo i
            idx    = 0

            # Pré-sorteia candidatos para cada slot (uma vez só)
            candidatos_slot = []
            for h in horarios_validos:
                cands = disponivel_em[h][:]
                # Ordena: menos disponibilidades totais e menos plantões atuais
                # (plantões = 0 aqui; vai ser re-ordenado dinamicamente abaixo)
                random.shuffle(cands)
                candidatos_slot.append(cands)

            while idx < N:
                h      = horarios_validos[idx]
                cands  = candidatos_slot[idx]

                # Ordena dinamicamente pelo estado atual de plantões + raridade
                # Só reordena quando entramos neste slot pela primeira vez (stack == 0)
                if stack[idx] == 0:
                    cands.sort(key=lambda i: (plantoes[i], n_disp[i]))

                encontrou = False
                while stack[idx] < len(cands):
                    c = cands[stack[idx]]
                    stack[idx] += 1
                    if plantoes[c] < 2:
                        alocacao[h] = c
                        plantoes[c] += 1
                        idx += 1
                        encontrou = True
                        break

                if not encontrou:
                    # Backtrack
                    alocacao[h] = -1
                    stack[idx]  = 0
                    if idx == 0:
                        break   # sem solução
                    idx -= 1
                    h_prev = horarios_validos[idx]
                    c_prev = alocacao[h_prev]
                    if c_prev != -1:
                        plantoes[c_prev] -= 1
                    alocacao[h_prev] = -1

        # Copia plantões finais para a estrutura original
        for i, nome in enumerate(nomes):
            diretores[nome]["plantoes"] = plantoes[i]

        # ============================================================
        # ALERTAS FINAIS
        # ============================================================
        alertas = []

        sem_disponibilidade = [n for n in nomes if not diretores[n]["disponibilidade"]]
        sem_plantao         = [n for n in nomes if diretores[n]["plantoes"] == 0 and diretores[n]["disponibilidade"]]
        acima_limite        = [n for n in nomes if diretores[n]["plantoes"] > 2]

        for h in horarios_validos:
            if alocacao[h] == -1:
                disponiveis = ", ".join(nomes[i] for i in disponivel_em[h])
                alertas.append(
                    f"🚫 {h.replace('_', ' ')}: ficou vazio — "
                    f"todos os disponíveis ({disponiveis}) já têm 2 plantões."
                )

        for h in todos_horarios:
            if not disponivel_em[h]:
                alertas.append(f"🚫 {h.replace('_', ' ')}: nenhum diretor marcou disponibilidade.")

        # ============================================================
        # MONTAR TABELA
        # ============================================================
        tabela = []
        for h in horas:
            linha = [h]
            for dia in dias_curto:
                chave = f"{dia}_{h}"
                i = alocacao[chave]
                linha.append(nomes[i] if i != -1 else "—")
            tabela.append(linha)

        colunas  = ["Horário"] + dias_curto
        df_final = pd.DataFrame(tabela, columns=colunas)

        st.subheader("📊 Escala Gerada")
        st.dataframe(df_final, use_container_width=True)

        # ============================================================
        # ESTATÍSTICAS
        # ============================================================
        stats = pd.DataFrame([
            {
                "Diretor": n,
                "Plantões": diretores[n]["plantoes"],
                "Disponibilidades": len(diretores[n]["disponibilidade"])
            }
            for n in nomes
        ]).sort_values("Plantões", ascending=False)

        st.subheader("📈 Estatísticas")
        st.dataframe(stats, use_container_width=True)

        # ============================================================
        # EXIBIR ALERTAS
        # ============================================================
        if acima_limite:
            st.error("🚨 BUG: diretores com mais de 2 plantões: " + ", ".join(acima_limite))
        if sem_disponibilidade:
            st.error("🚫 Sem disponibilidade alguma: " + ", ".join(sem_disponibilidade))
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
