import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from fpdf import FPDF
from io import BytesIO
from collections import Counter
import os

# ---------------- Page config ----------------
st.set_page_config(page_title="Analisador de Sentenças STF/STJ", layout="wide", initial_sidebar_state="expanded")

# ---------------- Theme toggle & logo upload ----------------
st.sidebar.markdown("## Aparência")
dark_mode = st.sidebar.checkbox("Modo escuro", value=False)
logo_file = st.sidebar.file_uploader("Upload de logo (opcional, PNG/JPG)", type=["png", "jpg", "jpeg"])

# CSS: light and dark themes
base_css = """
<style>
.footer-hidden {visibility: hidden;}
.card { background: var(--card-bg); padding: 14px; border-radius: 10px; box-shadow: 0 1px 6px rgba(10, 30, 60, 0.08); margin-bottom:12px; }
.header-title { font-size:26px; font-weight:700; color: var(--title-color); }
.muted { color: var(--muted-color); }
.custom-footer { padding:12px 0; text-align:center; font-size:13px; color: var(--footer-color); }
</style>
"""

if dark_mode:
    theme_vars = """
    :root {
      --bg-color: #0b1220;
      --container-bg: #071024;
      --card-bg: #071a2b;
      --title-color: #bfe1ff;
      --muted-color: #9aa6b2;
      --footer-color: #9fbff0;
      color-scheme: dark;
    }
    """
else:
    theme_vars = """
    :root {
      --bg-color: #f7fbff;
      --container-bg: #ffffff;
      --card-bg: #ffffff;
      --title-color: #08306b;
      --muted-color: #6b7280;
      --footer-color: #0b3d91;
      color-scheme: light;
    }
    """

st.markdown(f"<style>{theme_vars}</style>", unsafe_allow_html=True)
st.markdown(base_css, unsafe_allow_html=True)
st.markdown('<div class="header-title">🧾 Analisador de Sentenças — STF / STJ</div>', unsafe_allow_html=True)
st.markdown('<div class="muted">Buscador + Painel analítico para decisões dos tribunais superiores.</div>', unsafe_allow_html=True)
st.markdown("---")

# Mostrar logo
if logo_file:
    st.image(logo_file, width=120)

# ---------------- Sidebar upload ----------------
st.sidebar.markdown("---")
st.sidebar.header("Dados")
uploaded = st.sidebar.file_uploader("Carregar CSV (ID_Decisao, Tribunal, Ementa, Resultado, Data opcional)", type=["csv"])

# Funções auxiliares
def load_csv(uploaded_file):
    if uploaded_file is not None:
        try:
            return pd.read_csv(uploaded_file)
        except Exception:
            uploaded_file.seek(0)
            try:
                return pd.read_csv(uploaded_file, encoding="utf-8-sig")
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding="latin1")
    return pd.DataFrame([{
        "ID_Decisao": 1,
        "Tribunal": "STF",
        "Ementa": "Dano moral; responsabilidade civil.",
        "Resultado": "Procedente",
        "Data": "2023-05-12"
    }])

def count_keywords(df, col, keywords):
    kw = [k.strip().lower() for k in keywords if k.strip()]
    counts = {k: 0 for k in kw}
    mask = [False] * len(df)
    texts = df[col].fillna("").astype(str)
    for i, t in enumerate(texts):
        low = t.lower()
        for k in kw:
            if k in low:
                counts[k] += 1
                mask[i] = True
    return counts, mask

def make_wordcloud(series, extra_sw=None):
    text = " ".join(series.fillna("").astype(str).tolist()).lower()
    stopwords = set(STOPWORDS)
    if extra_sw:
        for s in extra_sw:
            stopwords.add(s.strip().lower())
    wc = WordCloud(
        width=800,
        height=400,
        background_color="black" if dark_mode else "white",
        stopwords=stopwords,
        collocations=False
    ).generate(text)
    return wc

def fig_to_png_bytes_matplotlib(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf.read()

def create_pdf_report(freq_df, matched_df, fig_res_bytes, fig_trib_bytes, wc_bytes):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "Relatório de Análise - Analisador de Sentenças STF/STJ", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, "Autores: Nicolly Soares Mota; Maria Eduarda de Bustamante Fontoura")
    pdf.ln(4)

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, "Frequência de termos:", ln=True)
    pdf.ln(2)
    for idx, row in freq_df.iterrows():
        pdf.cell(0, 6, f"{row['Termo']}: {row['Contagem']}", ln=True)
    pdf.ln(6)

    for img_bytes, caption in [(fig_res_bytes, "Distribuição de Resultados"), (fig_trib_bytes, "Distribuição por Tribunal"), (wc_bytes, "Nuvem de Palavras")]:
        if img_bytes:
            fname = "tmp_img.png"
            with open(fname, "wb") as f:
                f.write(img_bytes)
            pdf.set_font("Arial", size=11)
            pdf.cell(0, 6, caption, ln=True)
            pdf.image(fname, w=170)
            os.remove(fname)
            pdf.ln(4)

    pdf.add_page()
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, "Amostra de decisões encontradas:", ln=True)
    pdf.ln(2)
    for i, row in matched_df.head(10).iterrows():
        pdf.multi_cell(0, 5, f"{row['ID_Decisao']} | {row['Tribunal']} | {row['Resultado']} | {row['Ementa'][:80]}...")
        pdf.ln(1)

    out = BytesIO()
    out.write(pdf.output(dest="S").encode("latin-1", errors="replace"))
    out.seek(0)
    return out.read()

# ---------------- Load data ----------------
df = load_csv(uploaded)
df["Ementa"] = df["Ementa"].astype(str)
if "Data" in df.columns:
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

# ---------------- Tabs ----------------
tab1, tab2, tab3 = st.tabs(["🔍 Buscador", "📈 Análise", "ℹ️ Sobre"])

# ===== BUSCADOR =====
with tab1:
    st.subheader("🔎 Buscador de Jurisprudência")
    col1, col2 = st.columns([3, 1])
    with col1:
        search_q = st.text_input("Pesquisar termo na ementa", value="")
    with col2:
        tribunal_sel = st.selectbox("Tribunal", ["Ambos", "STF", "STJ"])

    with st.expander("Filtros avançados"):
        result_opts = sorted(df["Resultado"].dropna().unique())
        resultado_sel = st.multiselect("Resultado", result_opts, default=result_opts)
        if "Data" in df.columns:
            years = sorted(df["Data"].dt.year.dropna().unique())
            year_sel = st.multiselect("Ano", options=years, default=years)
        else:
            year_sel = []
        per_page = st.number_input("Resultados por página", min_value=5, max_value=50, value=10, step=5)

    # aplicar filtros
    results = df.copy()
    if tribunal_sel != "Ambos":
        results = results[results["Tribunal"].str.upper() == tribunal_sel.upper()]
    if search_q.strip():
        results = results[results["Ementa"].str.lower().str.contains(search_q.lower(), na=False)]
    if resultado_sel:
        results = results[results["Resultado"].isin(resultado_sel)]
    if year_sel and "Data" in results.columns:
        results = results[results["Data"].dt.year.isin(year_sel)]

    st.markdown(f"**Resultados encontrados: {len(results)}**")
    st.markdown("---")

    # Paginação
    results = results.sort_values(by="Data", ascending=False) if "Data" in results.columns else results
    page = st.session_state.get("page", 1)
    total_pages = max(1, (len(results) + per_page - 1) // per_page)
    colp1, colp2 = st.columns([1, 1])
    if colp1.button("◀ Anterior") and page > 1:
        page -= 1
    if colp2.button("Próxima ▶") and page < total_pages:
        page += 1
    st.session_state["page"] = page

    start, end = (page - 1) * per_page, (page - 1) * per_page + per_page
    for _, r in results.iloc[start:end].iterrows():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**{r['Tribunal']}** • {r['Resultado']} — *{r.get('Data','') if pd.notna(r.get('Data')) else ''}*")
        st.write(r['Ementa'][:300] + ("..." if len(r['Ementa']) > 300 else ""))
        if st.button("Ver mais", key=f"see_{r['ID_Decisao']}"):
            st.session_state["selected_id"] = r["ID_Decisao"]
        st.markdown('</div>', unsafe_allow_html=True)

    # Exibir decisão selecionada
    if "selected_id" in st.session_state:
        try:
            rec = df[df["ID_Decisao"] == st.session_state["selected_id"]]
            if not rec.empty:
                rec = rec.iloc[0]
                st.markdown("---")
                st.subheader(f"Decisão ID {int(rec['ID_Decisao'])}")
                st.write(f"**Tribunal:** {rec['Tribunal']}")
                st.write(f"**Resultado:** {rec['Resultado']}")
                if "Data" in df.columns:
                    st.write(f"**Data:** {pd.to_datetime(rec['Data']).date()}")
                st.write("**Ementa completa:**")
                st.write(rec["Ementa"])
                if st.button("Fechar"):
                    del st.session_state["selected_id"]
        except Exception as e:
            st.warning(f"Erro ao exibir decisão: {e}")

    st.markdown("---")
    st.markdown(f"Página {page} de {total_pages}")

# ===== ANÁLISE =====
with tab2:
    st.subheader("📈 Análise de Termos e Relatórios")
    col1, col2 = st.columns([3, 1])
    with col1:
        keywords_input = st.text_input("Termos-chave (separados por vírgula)", "dano moral, inconstitucionalidade, repercussão geral")
        extra_sw_text = st.text_area("Stopwords adicionais", "de\na\no\nem\npara\ncom\npor\nque")
    with col2:
        tribunal_an = st.selectbox("Tribunal (Análise)", ["Ambos", "STF", "STJ"])
        if "Data" in df.columns:
            years_all = sorted(df["Data"].dt.year.dropna().unique())
            year_an = st.multiselect("Anos (Análise)", years_all, default=years_all)
        else:
            year_an = []
        run = st.button("Rodar Análise")

    df_an = df.copy()
    if tribunal_an != "Ambos":
        df_an = df_an[df_an["Tribunal"].str.upper() == tribunal_an.upper()]
    if year_an and "Data" in df_an.columns:
        df_an = df_an[df_an["Data"].dt.year.isin(year_an)]

    if run or st.session_state.get("analysis_done") is None:
        st.session_state["analysis_done"] = True
        keywords = [k.strip().lower() for k in keywords_input.split(",") if k.strip()]
        extra_sw = [s.strip().lower() for s in extra_sw_text.splitlines() if s.strip()]
        counts, mask = count_keywords(df_an, "Ementa", keywords)
        freq_df = pd.DataFrame.from_dict(counts, orient="index", columns=["Contagem"]).reset_index().rename(columns={"index": "Termo"})
        matched_df = df_an.loc[mask]

        st.subheader("📈 Frequência de termos")
        st.table(freq_df)

        st.subheader("📊 Gráficos")
        colg1, colg2 = st.columns(2)
        with colg1:
            res_counts = df_an["Resultado"].value_counts().reset_index()
            res_counts.columns = ["Resultado", "Quantidade"]
            fig_res = px.bar(res_counts, x="Resultado", y="Quantidade", title="Distribuição de Resultados", text="Quantidade")
            st.plotly_chart(fig_res, use_container_width=True)
        with colg2:
            trib_counts = df_an["Tribunal"].value_counts().reset_index()
            trib_counts.columns = ["Tribunal", "Quantidade"]
            fig_trib = px.pie(trib_counts, names="Tribunal", values="Quantidade", title="Proporção por Tribunal")
            st.plotly_chart(fig_trib, use_container_width=True)

        st.subheader("☁️ Nuvem de Palavras")
        wc = make_wordcloud(df_an["Ementa"], extra_sw)
        fig_wc, ax = plt.subplots(figsize=(10, 4))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig_wc)

        st.subheader("🏆 Top 20 palavras")
        all_text = " ".join(df_an["Ementa"].fillna("").astype(str).tolist()).lower()
        words = [w for w in all_text.split() if len(w) > 3 and w.isalpha() and w not in set(extra_sw)]
        top = pd.DataFrame(Counter(words).most_common(20), columns=["Palavra", "Frequência"])
        st.table(top)

        st.subheader("📥 Exportar relatórios")
        freq_csv = freq_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV - Frequência de termos", data=freq_csv, file_name="frequencia_termos.csv", mime="text/csv")
        csv_matched = matched_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV - Decisões encontradas", data=csv_matched, file_name="decisoes_encontradas.csv", mime="text/csv")

        # PDF
        try:
            img_res = fig_res.to_image(format="png")
            img_trib = fig_trib.to_image(format="png")
        except Exception:
            img_res = fig_to_png_bytes_matplotlib(plt.figure())
            img_trib = fig_to_png_bytes_matplotlib(plt.figure())

        buf_wc = BytesIO()
        fig_wc.savefig(buf_wc, format="png", bbox_inches="tight")
        buf_wc.seek(0)
        wc_bytes = buf_wc.read()
        pdf_bytes = create_pdf_report(freq_df, matched_df, img_res, img_trib, wc_bytes)
        st.download_button("Download PDF - Relatório de análise", data=pdf_bytes, file_name="relatorio_analise.pdf", mime="application/pdf")

# ===== SOBRE =====
with tab3:
    st.subheader("ℹ️ Sobre o projeto")
    st.write("""
    **Analisador de Sentenças STF/STJ** — projeto acadêmico (Programação para Advogados).
    Permite pesquisar e filtrar ementas, analisar frequência de termos, gerar nuvens de palavras e exportar relatórios em CSV/PDF.
    """)
    st.write("**Autoras:** Nicolly Soares Mota; Maria Eduarda de Bustamante Fontoura")
    st.markdown("---")
    st.write("Instruções rápidas: carregue seu CSV (ou gere exemplo), use a aba Buscador para pesquisa e a aba Análise para relatórios.")

st.markdown("<div class='custom-footer'>© 2025 — Nicolly Soares Mota & Maria Eduarda de Bustamante Fontoura — Analisador de Sentenças STF/STJ</div>", unsafe_allow_html=True)
