# app.py
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

# CSS: light and dark basic themes (affecting backgrounds, cards and text)
base_css = """
<style>
.footer-hidden {visibility: hidden;}
.card { background: var(--card-bg); padding: 14px; border-radius: 10px; box-shadow: 0 1px 6px rgba(10, 30, 60, 0.08); margin-bottom:12px; }
.header-title { font-size:26px; font-weight:700; color: var(--title-color); }
.muted { color: var(--muted-color); }
.custom-footer { padding:12px 0; text-align:center; font-size:13px; color: var(--footer-color); }
</style>
"""

# Define CSS variables for light and dark
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
st.markdown('<div style="margin-bottom:8px;" class="header-title">🧾 Analisador de Sentenças — STF / STJ</div>', unsafe_allow_html=True)
st.markdown('<div class="muted">Buscador + Painel analítico para decisões dos tribunais superiores.</div>', unsafe_allow_html=True)
st.markdown("---")

# Show logo if uploaded
if logo_file:
    st.image(logo_file, width=120)

# ---------------- Sidebar: data upload & helpers ----------------
st.sidebar.markdown("---")
st.sidebar.header("Dados")
uploaded = st.sidebar.file_uploader("Carregar CSV (ID_Decisao, Tribunal, Ementa, Resultado, opcional: Data)", type=["csv"])
if st.sidebar.button("Gerar CSV de exemplo"):
    # small helper to create example file in memory
    def gen_example_df(n=60):
        import random
        sample_ementas = [
            'Dano moral em contrato de consumo; procedente; responsabilidade do fornecedor',
            'Habeas corpus improcedente; cerceamento de defesa não configurado',
            'Repercussão geral reconhecida; inconstitucionalidade parcial',
            'Contrato bancário e cobrança indevida; procedente',
            'Questão tributária; improcedente'
        ]
        resultados = ['Procedente', 'Improcedente', 'Parcialmente Procedente']
        tribunais = ['STF', 'STJ']
        data = []
        for i in range(1, n+1):
            ano = 2015 + (i % 11)
            mes = (i % 12) + 1
            dia = (i % 27) + 1
            data.append({
                'ID_Decisao': i,
                'Tribunal': random.choice(tribunais),
                'Ementa': random.choice(sample_ementas),
                'Resultado': random.choice(resultados),
                'Data': f"{ano}-{mes:02d}-{dia:02d}"
            })
        return pd.DataFrame(data)
    example_df = gen_example_df()
    st.session_state['_example_csv'] = example_df.to_csv(index=False).encode('utf-8')
    st.sidebar.success("CSV de exemplo gerado na sessão. Agora escolha 'Usar CSV de Exemplo' no painel principal.")

# ---------------- Helpers ----------------
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
    # fallback: session example or local file
    if '_example_csv' in st.session_state:
        from io import BytesIO
        return pd.read_csv(BytesIO(st.session_state['_example_csv']))
    if os.path.exists("decisoes_stf_stj.csv"):
        try:
            return pd.read_csv("decisoes_stf_stj.csv")
        except Exception:
            return pd.read_csv("decisoes_stf_stj.csv", encoding="latin1")
    # last fallback: tiny sample
    return pd.DataFrame([{
        'ID_Decisao':1,'Tribunal':'STF','Ementa':'Dano moral; responsabilidade','Resultado':'Procedente','Data':'2021-01-10'
    }])

def count_keywords(df, col, keywords):
    kw = [k.strip().lower() for k in keywords if k.strip()]
    counts = {k:0 for k in kw}
    mask = [False]*len(df)
    texts = df[col].fillna('').astype(str)
    for i, t in enumerate(texts):
        low = t.lower()
        for k in kw:
            if k in low:
                counts[k] += 1
                mask[i] = True
    return counts, mask

def make_wordcloud(series, extra_sw=None, width=800, height=400):
    text = " ".join(series.fillna('').astype(str).tolist()).lower()
    stopwords = set(STOPWORDS)
    if extra_sw:
        for s in extra_sw:
            stopwords.add(s.strip().lower())
    wc = WordCloud(width=width, height=height, background_color='black' if dark_mode else 'white',
                   stopwords=stopwords, collocations=False).generate(text)
    return wc

def fig_to_png_bytes_matplotlib(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    return buf.read()

def create_pdf_report(freq_df, matched_df, fig_res_bytes, fig_trib_bytes, wc_bytes, title="Relatório de Análise"):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, title, ln=True)
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
    cols = list(matched_df.columns)
    for i, row in matched_df.head(12).iterrows():
        line = " | ".join(str(row[c]) for c in cols if c in matched_df.columns)
        pdf.multi_cell(0, 5, line)
        pdf.ln(1)

    out = BytesIO()
    out.write(pdf.output(dest='S').encode('latin-1', errors='replace'))
    out.seek(0)
    return out.read()

# ---------------- Load data ----------------
df = load_csv(uploaded)
required_cols = {'ID_Decisao', 'Tribunal', 'Ementa', 'Resultado'}
if not required_cols.issubset(set(df.columns)):
    st.error(f"Arquivo precisa ter colunas: {required_cols}. Colunas encontradas: {list(df.columns)}")
    st.stop()

df['Ementa'] = df['Ementa'].astype(str)
if 'Data' in df.columns:
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

# ---------------- Tabs ----------------
tab1, tab2, tab3 = st.tabs(["🔍 Buscador", "📈 Análise", "ℹ️ Sobre"])

# ----- BUSCADOR -----
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🔎 Buscar e filtrar ementas")
    col_s1, col_s2 = st.columns([3,1])
    with col_s1:
        search_q = st.text_input("Pesquisar (palavras ou expressão)", value="")
    with col_s2:
        tribunal_sel = st.selectbox("Tribunal", ["Ambos", "STF", "STJ"])
    with st.expander("Filtros avançados"):
        res_opts = sorted(df['Resultado'].dropna().unique())
        resultado_sel = st.multiselect("Resultado", options=res_opts, default=res_opts)
        if 'Data' in df.columns:
            years = sorted(df['Data'].dt.year.dropna().unique())
            year_sel = st.multiselect("Ano", options=years, default=years)
        else:
            year_sel = []
        per_page = st.number_input("Resultados por página", min_value=5, max_value=50, value=10, step=5)

    st.markdown("</div>", unsafe_allow_html=True)

    # filter
    results = df.copy()
    if tribunal_sel != "Ambos":
        results = results[results['Tribunal'].str.upper() == tribunal_sel.upper()]
    if search_q.strip():
        q = search_q.strip().lower()
        results = results[results['Ementa'].str.lower().str.contains(q, na=False)]
    if resultado_sel:
        results = results[results['Resultado'].isin(resultado_sel)]
    if year_sel and 'Data' in results.columns:
        results = results[results['Data'].dt.year.isin(year_sel)]

    st.markdown(f"**Resultados encontrados: {len(results)}**")
    st.markdown("---")

    # pagination
    results = results.sort_values(by='Data', ascending=False) if 'Data' in results.columns else results
    page = st.session_state.get("page", 1)
    total_pages = max(1, (len(results) + per_page - 1) // per_page)
    colp1, colp2 = st.columns([1,1])
    if colp1.button("◀ Anterior") and page > 1:
        page -= 1
    if colp2.button("Próxima ▶") and page < total_pages:
        page += 1
    st.session_state['page'] = page

    start = (page - 1) * per_page
    end = start + per_page
    for _, r in results.iloc[start:end].iterrows():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        c1, c2 = st.columns([6,1])
        with c1:
            st.markdown(f"**ID {r['ID_Decisao']} — {r.get('Tribunal','')}**  •  {r.get('Resultado','')}")
            if 'Data' in df.columns and pd.notna(r.get('Data')):
                st.markdown(f"*{pd.to_datetime(r.get('Data')).date()}*")
            txt = str(r['Ementa'])
            excerpt = (txt[:380] + '...') if len(txt) > 380 else txt
            st.write(excerpt)
        with c2:
            if st.button("Ver mais", key=f"see_{r['ID_Decisao']}"):
                st.experimental_set_query_params(id=r['ID_Decisao'])
        st.markdown('</div>', unsafe_allow_html=True)

    # show expanded if requested
    params = st.experimental_get_query_params()
    if "id" in params:
        try:
            sel = int(params["id"][0])
            rec = df[df['ID_Decisao'] == sel]
            if not rec.empty:
                rec = rec.iloc[0]
                st.markdown("---")
                st.subheader(f"Decisão ID {int(rec['ID_Decisao'])}")
                st.write(f"**Tribunal:** {rec.get('Tribunal','')}")
                st.write(f"**Resultado:** {rec.get('Resultado','')}")
                if 'Data' in df.columns:
                    st.write(f"**Data:** {pd.to_datetime(rec.get('Data')).date()}")
                st.write("**Ementa completa:**")
                st.write(rec.get('Ementa',''))
                if st.button("Fechar"):
                    st.experimental_set_query_params()

    st.markdown("---")
    st.markdown(f"Página {page} de {total_pages}")

# ----- ANALYSIS -----
with tab2:
    st.subheader("📈 Painel Analítico")
    k_col, s_col = st.columns([3,1])
    with k_col:
        key_input = st.text_input("Termos-chave (vírgula-separados)", value="dano moral, inconstitucionalidade, repercussão geral")
        extra_sw_text = st.text_area("Stopwords adicionais (uma por linha)", value="de\na\no\nem\npara\ncom\npor\nque", height=120)
    with s_col:
        tribunal_an = st.selectbox("Tribunal (Análise)", ["Ambos", "STF", "STJ"])
        if 'Data' in df.columns:
            years_all = sorted(df['Data'].dt.year.dropna().unique())
            year_an = st.multiselect("Anos (Análise)", options=years_all, default=years_all)
        else:
            year_an = []
        run = st.button("Rodar Análise")

    df_an = df.copy()
    if tribunal_an != "Ambos":
        df_an = df_an[df_an['Tribunal'].str.upper() == tribunal_an.upper()]
    if year_an and 'Data' in df_an.columns:
        df_an = df_an[df_an['Data'].dt.year.isin(year_an)]

    if run or st.session_state.get("analysis_done") is None:
        st.session_state["analysis_done"] = True
        keywords = [k.strip().lower() for k in key_input.split(",") if k.strip()]
        extra_sw = [s.strip().lower() for s in extra_sw_text.splitlines() if s.strip()]
        counts, mask = count_keywords(df_an, 'Ementa', keywords)
        freq_df = pd.DataFrame.from_dict(counts, orient='index', columns=['Contagem']).reset_index().rename(columns={'index':'Termo'})
        matched_df = df_an.loc[mask, ['ID_Decisao','Tribunal','Resultado','Ementa','Data']] if 'Data' in df_an.columns else df_an.loc[mask, ['ID_Decisao','Tribunal','Resultado','Ementa']]

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📈 Frequência de termos")
        st.table(freq_df)
        st.markdown('</div>', unsafe_allow_html=True)

        st.subheader("📊 Gráficos")
        c1, c2 = st.columns(2)
        with c1:
            res_counts = df_an['Resultado'].value_counts().reset_index()
            res_counts.columns = ['Resultado','Quantidade']
            fig_res = px.bar(res_counts, x='Resultado', y='Quantidade', title='Distribuição de Resultados', text='Quantidade')
            st.plotly_chart(fig_res, use_container_width=True)
        with c2:
            trib_counts = df_an['Tribunal'].value_counts().reset_index()
            trib_counts.columns = ['Tribunal','Quantidade']
            fig_trib = px.pie(trib_counts, names='Tribunal', values='Quantidade', title='Proporção por Tribunal')
            st.plotly_chart(fig_trib, use_container_width=True)

        st.subheader("☁️ Nuvem de palavras")
        wc = make_wordcloud(df_an['Ementa'], extra_sw=extra_sw)
        fig_wc, ax = plt.subplots(figsize=(10,4))
        ax.imshow(wc, interpolation='bilinear')
        ax.axis('off')
        st.pyplot(fig_wc)

        st.subheader("🏆 Ranking de Palavras (Top 20)")
        all_text = " ".join(df_an['Ementa'].fillna('').astype(str).tolist()).lower()
        words = [w for w in all_text.split() if len(w) > 3 and w.isalpha() and w not in set(extra_sw)]
        top = pd.DataFrame(Counter(words).most_common(20), columns=['Palavra','Frequência'])
        st.table(top)

        st.markdown("---")
        st.subheader("📥 Exportar relatórios")
        csv_matched = matched_df.to_csv(index=False).encode('utf-8') if not matched_df.empty else b""
        st.download_button("Download CSV - Decisões encontradas", data=csv_matched, file_name="decisoes_encontradas.csv", mime="text/csv")
        freq_csv = freq_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV - Frequência", data=freq_csv, file_name="frequencia_termos.csv", mime="text/csv")

        # prepare pdf images
        try:
            img_res = fig_res.to_image(format='png')
            img_trib = fig_trib.to_image(format='png')
        except Exception:
            figr, axr = plt.subplots()
            axr.bar(res_counts['Resultado'], res_counts['Quantidade'])
            axr.set_title('Distribuição de Resultados')
            img_res = fig_to_png_bytes_matplotlib(figr)
            figt, axt = plt.subplots()
            axt.pie(trib_counts['Quantidade'], labels=trib_counts['Tribunal'], autopct='%1.1f%%')
            axt.set_title('Proporção por Tribunal')
            img_trib = fig_to_png_bytes_matplotlib(figt)

        buf = BytesIO(); fig_wc.savefig(buf, format='png', bbox_inches='tight'); buf.seek(0); wc_bytes = buf.read()
        pdf_bytes = create_pdf_report(freq_df, matched_df, img_res, img_trib, wc_bytes)
        st.download_button("Download - Relatório em PDF", data=pdf_bytes, file_name="relatorio_analise.pdf", mime="application/pdf")

# ----- Sobre -----
with tab3:
    st.subheader("ℹ️ Sobre o projeto")
    st.write("""
        **Analisador de Sentenças STF/STJ** — projeto acadêmico (Programação para Advogados).
        Permite pesquisar e filtrar ementas, analisar frequência de termos, visualizar nuvem de palavras
        e exportar relatórios em CSV/PDF.
    """)
    st.write("**Autoras:** Nicolly Soares Mota; Maria Eduarda de Bustamante Fontoura")
    st.markdown("---")
    st.write("Instruções rápidas: carregue seu CSV (ou gere exemplo), vá na aba Buscador para filtrar e na aba Análise para produzir relatórios. Para publicar: envie para o GitHub e conecte no Streamlit Cloud.")

# Footer
st.markdown("<div class='custom-footer'>© 2025 — Nicolly Soares Mota & Maria Eduarda de Bustamante Fontoura — Analisador de Sentenças STF/STJ</div>", unsafe_allow_html=True)
