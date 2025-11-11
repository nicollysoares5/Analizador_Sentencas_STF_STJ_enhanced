# app.py (Versão v4 — correções: busca universal, layout melhor, links e PDF em memória)
import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from io import BytesIO
from collections import Counter
import os
import html
import re

# PDF generation using reportlab (works in-memory)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# ---------------- Page config ----------------
st.set_page_config(page_title="Analisador de Sentenças STF/STJ", layout="wide", initial_sidebar_state="expanded")

# ---------------- Theme and basic CSS ----------------
PRIMARY = "#0b3d91"
st.markdown(f"""
    <style>
    .title-big {{ font-size:28px; font-weight:700; color: {PRIMARY}; margin-bottom:6px; }}
    .muted {{ color:#6b7280; margin-bottom:12px; }}
    .card {{ background: #ffffff; padding:14px; border-radius:10px; box-shadow: 0 1px 6px rgba(10,30,60,0.06); margin-bottom:12px; }}
    .small-muted {{ color:#8892a6; font-size:13px; }}
    footer {{visibility: hidden;}}
    .footer-custom {{ text-align:center; color:{PRIMARY}; padding:12px 0; font-size:13px; }}
    a.btn-link {{ background: {PRIMARY}; color: white; padding: 6px 10px; border-radius:6px; text-decoration:none; }}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-big">🧾 Analisador de Sentenças — STF / STJ</div>', unsafe_allow_html=True)
st.markdown('<div class="muted">Busque e analise ementas — filtros, gráficos, nuvem de palavras e exportação.</div>', unsafe_allow_html=True)

# ---------------- Sidebar (data upload + options) ----------------
with st.sidebar:
    st.header("Dados")
    uploaded = st.file_uploader("Carregar CSV (colunas mínimas: ID_Decisao, Tribunal, Ementa, Resultado; opcional: Data, Link)", type=["csv"])
    st.markdown("Se nenhum CSV for enviado, uma base de exemplo será usada.")
    st.markdown("---")
    st.header("Aparência")
    dark = st.checkbox("Modo escuro (apenas estética)", value=False)
    st.markdown("---")
    st.markdown("Autores: **Nicolly Soares Mota** • **Maria Eduarda de Bustamante Fontoura**")
    st.markdown("---")

# ---------------- Helpers ----------------
def load_csv_file(fileobj):
    """Try reading with common encodings."""
    try:
        return pd.read_csv(fileobj)
    except Exception:
        try:
            fileobj.seek(0)
            return pd.read_csv(fileobj, encoding="utf-8-sig")
        except Exception:
            fileobj.seek(0)
            return pd.read_csv(fileobj, encoding="latin1")

def generate_sample_df(n=60):
    import random
    sample_ementas = [
        'Dano moral em contrato de consumo; procedente; responsabilidade do fornecedor',
        'Habeas corpus improcedente; cerceamento de defesa não configurado',
        'Repercussão geral reconhecida; inconstitucionalidade parcial',
        'Contrato bancário e cobrança indevida; procedente',
        'Questão tributária; improcedente',
        'Direito de família; partilha e alimentos; parcialmente procedente',
        'Licitação e responsabilidade; improcedente',
        'Indenização por acidente; procedente',
    ]
    resultados = ['Procedente', 'Improcedente', 'Parcialmente Procedente']
    tribunais = ['STF', 'STJ']
    data = []
    for i in range(1, n+1):
        ano = 2015 + (i % 10)
        mes = (i % 12) + 1
        dia = (i % 27) + 1
        data.append({
            'ID_Decisao': i,
            'Tribunal': random.choice(tribunais),
            'Ementa': random.choice(sample_ementas),
            'Resultado': random.choice(resultados),
            'Data': f"{ano}-{mes:02d}-{dia:02d}",
            'Link': f"https://example.org/decision/{i}"
        })
    return pd.DataFrame(data)

def safe_contains(series, q):
    """Case-insensitive contains with regex-escape; handle NaN."""
    if q.strip() == "":
        # if empty query, return all True
        return pd.Series([True]*len(series), index=series.index)
    try:
        pattern = re.escape(q.strip().lower())
        return series.fillna("").astype(str).str.lower().str.contains(pattern, na=False)
    except Exception:
        # fallback to simple substring
        return series.fillna("").astype(str).str.lower().str.contains(q.strip().lower(), na=False)

def count_keywords_in_texts(df, col, keywords):
    kw = [k.strip().lower() for k in keywords if k.strip()]
    counts = {k: 0 for k in kw}
    mask = pd.Series([False]*len(df), index=df.index)
    texts = df[col].fillna("").astype(str)
    for k in kw:
        match = texts.str.lower().str.contains(re.escape(k), na=False)
        counts[k] = int(match.sum())
        mask = mask | match
    return counts, mask

def make_wordcloud_bytes(text_series, extra_stopwords=None, width=800, height=400, background="white"):
    """Gera a nuvem de palavras, tratando casos vazios."""
    text = " ".join(text_series.fillna("").astype(str).tolist()).lower().strip()
    if not text or len(text.split()) == 0:
        # cria uma imagem branca simples com aviso
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (width, height), color=background)
        draw = ImageDraw.Draw(img)
        msg = "Sem palavras para gerar a nuvem"
        draw.text((width // 10, height // 2 - 10), msg, fill="gray")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    stopwords = set(STOPWORDS)
    if extra_stopwords:
        for s in extra_stopwords:
            stopwords.add(s.strip().lower())

    wc = WordCloud(
        width=width,
        height=height,
        background_color=background,
        stopwords=stopwords,
        collocations=False
    ).generate(text)

    buf = BytesIO()
    wc.to_image().save(buf, format="PNG")
    buf.seek(0)
    return buf


def fig_to_png_bytes_matplotlib(fig):
    buf = BytesIO()
    fig.savefig(buf, format="PNG", bbox_inches="tight")
    buf.seek(0)
    return buf

def create_pdf_report_bytes(freq_df, matched_df, fig_res_bytes, fig_trib_bytes, wc_bytes):
    """Generate PDF in-memory using reportlab. Returns bytes."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 40
    y = height - margin

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Relatório de Análise - Analisador de Sentenças STF/STJ")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, "Autores: Nicolly Soares Mota; Maria Eduarda de Bustamante Fontoura")
    y -= 25

    # Frequency table (simple)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Frequência de termos:")
    y -= 16
    c.setFont("Helvetica", 10)
    for idx, row in freq_df.iterrows():
        text = f"{row['Termo']}: {row['Contagem']}"
        c.drawString(margin, y, text)
        y -= 12
        if y < margin + 120:
            c.showPage()
            y = height - margin

    # Images (charts)
    def draw_image_from_bytes(img_bytes, caption):
        nonlocal y
        if img_bytes is None:
            return
        img = ImageReader(BytesIO(img_bytes))
        img_w = width - 2*margin
        img_h = img_w * 0.45  # aspect ratio
        if y - img_h < margin:
            c.showPage()
            y = height - margin
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, caption)
        y -= 14
        c.drawImage(img, margin, y - img_h, width=img_w, height=img_h)
        y -= img_h + 12

    draw_image_from_bytes(fig_res_bytes, "Distribuição de Resultados")
    draw_image_from_bytes(fig_trib_bytes, "Distribuição por Tribunal")
    draw_image_from_bytes(wc_bytes.getvalue() if isinstance(wc_bytes, BytesIO) else wc_bytes, "Nuvem de Palavras")

    # Sample decisions
    if not matched_df.empty:
        c.showPage()
        y = height - margin
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Amostra de decisões encontradas:")
        y -= 16
        c.setFont("Helvetica", 9)
        for _, row in matched_df.head(20).iterrows():
            linha = f"ID {row.get('ID_Decisao','')} | {row.get('Tribunal','')} | {row.get('Resultado','')} | {str(row.get('Ementa',''))[:120]}..."
            text_lines = c.beginText(margin, y)
            text_lines.textLines(linha)
            c.drawText(text_lines)
            y -= 14
            if y < margin + 50:
                c.showPage()
                y = height - margin

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# ---------------- Load CSV ----------------
if uploaded is not None:
    try:
        df = load_csv_file(uploaded)
    except Exception as e:
        st.error(f"Erro ao ler o CSV: {e}")
        st.stop()
else:
    # attempt to load a local fallback file
    local_path = "decisoes_stf_stj.csv"
    if os.path.exists(local_path):
        try:
            df = pd.read_csv(local_path)
        except Exception:
            df = pd.read_csv(local_path, encoding="latin1")
    else:
        df = generate_sample_df()

# minimal validation
req_cols = {"ID_Decisao", "Tribunal", "Ementa", "Resultado"}
if not req_cols.issubset(set(df.columns)):
    st.error(f"CSV precisa conter colunas mínimas: {req_cols}. Colunas encontradas: {list(df.columns)}")
    st.stop()

# normalize
df["Ementa"] = df["Ementa"].astype(str)
if "Data" in df.columns:
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

# ---------------- Top search bar (center) ----------------
st.markdown("---")
search_col1, search_col2, search_col3 = st.columns([1,6,1])
with search_col2:
    q = st.text_input("🔎 Pesquisar ementa (qualquer palavra ou expressão)", value="", placeholder="Ex.: licitação irregular")
    search_button = st.button("Pesquisar")

# ---------------- Filters row ----------------
f1, f2, f3, f4 = st.columns([2,2,2,2])
with f1:
    tribunal_filter = st.selectbox("Tribunal", ["Ambos", "STF", "STJ"])
with f2:
    if "Data" in df.columns:
        years = sorted(df["Data"].dt.year.dropna().unique())
        year_filter = st.multiselect("Ano", options=years, default=years)
    else:
        year_filter = []
with f3:
    result_options = sorted(df["Resultado"].dropna().unique())
    result_filter = st.multiselect("Resultado", options=result_options, default=result_options)
with f4:
    per_page = st.selectbox("Por página", options=[5,10,15,20], index=1)

st.markdown("---")

# ---------------- Apply search and filters ----------------
results = df.copy()
if tribunal_filter != "Ambos":
    results = results[results["Tribunal"].str.upper() == tribunal_filter.upper()]

if q.strip():
    # safe contains
    results = results[safe_contains(results["Ementa"], q)]

if result_filter:
    results = results[results["Resultado"].isin(result_filter)]

if year_filter and "Data" in results.columns:
    results = results[results["Data"].dt.year.isin(year_filter)]

results = results.sort_values(by="Data", ascending=False) if "Data" in results.columns else results

st.markdown(f"**Resultados:** {len(results)} encontrados")

# ---------------- Pagination and display as cards ----------------
page = st.session_state.get("page_search", 1)
total_pages = max(1, (len(results) + per_page - 1) // per_page)
col_prev, col_next = st.columns([1,1])
if col_prev.button("◀ Anterior") and page > 1:
    page -= 1
if col_next.button("Próxima ▶") and page < total_pages:
    page += 1
st.session_state["page_search"] = page

start = (page - 1) * per_page
end = start + per_page
for _, row in results.iloc[start:end].iterrows():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns([6,1])
    with c1:
        title = f"ID {row.get('ID_Decisao','')} — {row.get('Tribunal','')} • {row.get('Resultado','')}"
        st.markdown(f"**{html.escape(title)}**")
        if "Data" in df.columns and pd.notna(row.get("Data")):
            st.markdown(f"*{pd.to_datetime(row.get('Data')).date()}*")
        ementa_text = str(row.get("Ementa",""))
        excerpt = (ementa_text[:420] + "...") if len(ementa_text) > 420 else ementa_text
        st.write(excerpt)
    with c2:
        # link to original decision if exists
        if "Link" in df.columns and pd.notna(row.get("Link")) and str(row.get("Link")).strip() != "":
            url = row.get("Link")
            # HTML button-like link
            st.markdown(f'<a class="btn-link" href="{html.escape(url)}" target="_blank">Acessar decisão original</a>', unsafe_allow_html=True)
        # view more (expand)
        if st.button("Ver mais", key=f"more_{row.get('ID_Decisao')}"):
            st.session_state["selected_decision"] = int(row.get("ID_Decisao"))
    st.markdown('</div>', unsafe_allow_html=True)

# show expanded selected decision
if "selected_decision" in st.session_state:
    sel = st.session_state["selected_decision"]
    recs = df[df["ID_Decisao"] == sel]
    if not recs.empty:
        rec = recs.iloc[0]
        st.markdown("---")
        st.subheader(f"Decisão ID {int(rec['ID_Decisao'])}")
        st.write(f"**Tribunal:** {rec.get('Tribunal','')}")
        st.write(f"**Resultado:** {rec.get('Resultado','')}")
        if "Data" in df.columns:
            st.write(f"**Data:** {pd.to_datetime(rec.get('Data')).date()}")
        st.write("**Ementa completa:**")
        st.write(rec.get("Ementa",""))
        if "Link" in df.columns and pd.notna(rec.get("Link")) and str(rec.get("Link")).strip() != "":
            st.markdown(f'<a href="{html.escape(rec.get("Link"))}" target="_blank">🔗 Abrir decisão original</a>', unsafe_allow_html=True)
        if st.button("Fechar"):
            del st.session_state["selected_decision"]

st.markdown("---")

# ---------------- Analysis panel (separate) ----------------
st.header("📈 Painel de Análise")
col_k, col_o = st.columns([3,1])
with col_k:
    keywords_input = st.text_input("Termos de interesse (vírgula-separados) — usados para gerar tabela de frequência", value="dano moral, inconstitucionalidade")
with col_o:
    extra_stop = st.text_area("Stopwords (uma por linha) para nuvem", value="de\na\no\nem\npara\ncom\npor\nque", height=120)
run_analysis = st.button("Rodar Análise (com filtros aplicados acima)")

# Build df_an according to same current filters
df_an = results.copy()

if run_analysis or st.session_state.get("analysis_done") is None:
    st.session_state["analysis_done"] = True
    keywords = [k.strip().lower() for k in keywords_input.split(",") if k.strip()]
    extra_sw = [s.strip().lower() for s in extra_stop.splitlines() if s.strip()]

    counts, mask = count_keywords_in_texts(df_an, "Ementa", keywords) if keywords else ({}, pd.Series([False]*len(df_an)))
    freq_df = pd.DataFrame.from_dict(counts, orient="index", columns=["Contagem"]).reset_index().rename(columns={"index":"Termo"}) if counts else pd.DataFrame(columns=["Termo","Contagem"])
    matched_df = df_an[mask] if not df_an.empty else df_an.head(0)

    st.subheader("📈 Frequência de termos")
    st.table(freq_df if not freq_df.empty else pd.DataFrame([{"Termo":"(nenhum termo)", "Contagem":0}]))

    st.subheader("📊 Gráficos")
    colg1, colg2 = st.columns(2)
    with colg1:
        if not df_an.empty:
            res_counts = df_an["Resultado"].value_counts().reset_index()
            res_counts.columns = ["Resultado","Quantidade"]
            fig_res = px.bar(res_counts, x="Resultado", y="Quantidade", title="Distribuição de Resultados", text="Quantidade")
            st.plotly_chart(fig_res, use_container_width=True)
        else:
            st.info("Sem dados para gráfico de resultados.")
    with colg2:
        if not df_an.empty:
            trib_counts = df_an["Tribunal"].value_counts().reset_index()
            trib_counts.columns = ["Tribunal","Quantidade"]
            fig_trib = px.pie(trib_counts, names="Tribunal", values="Quantidade", title="Proporção por Tribunal")
            st.plotly_chart(fig_trib, use_container_width=True)
        else:
            st.info("Sem dados para gráfico por tribunal.")

    st.subheader("☁️ Nuvem de palavras")
    wc_buf = make_wordcloud_bytes(df_an["Ementa"], extra_stopwords=extra_sw, background=("black" if dark else "white"))
    fig_wc, ax = plt.subplots(figsize=(10,4))
    img = plt.imread(wc_buf)
    ax.imshow(img)
    ax.axis("off")
    st.pyplot(fig_wc)

    st.subheader("🏅 Top palavras (Top 20)")
    all_text = " ".join(df_an["Ementa"].fillna("").astype(str).tolist()).lower()
    words = [w for w in re.findall(r"\\b[a-zA-ZãÃõÕéÉíÍóÓúÚçÇ]+\\b", all_text) if len(w) > 3 and w not in set(extra_sw)]
    top = pd.DataFrame(Counter(words).most_common(20), columns=["Palavra","Frequência"])
    st.table(top)

    st.markdown("---")
    st.subheader("📥 Exportar relatórios")

    # Prepare images for PDF (use plotly .to_image if available; otherwise render simple matplotlib)
    try:
        fig_res_bytes = fig_res.to_image(format="png") if 'fig_res' in locals() else None
    except Exception:
        fig_res_bytes = None

    try:
        fig_trib_bytes = fig_trib.to_image(format="png") if 'fig_trib' in locals() else None
    except Exception:
        fig_trib_bytes = None

    # PDF bytes (reportlab)
    pdf_bytes = create_pdf_report_bytes(freq_df, matched_df, fig_res_bytes, fig_trib_bytes, wc_buf)

    # Downloads and CSVs
    freq_csv = freq_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV - Frequência de termos", data=freq_csv, file_name="frequencia_termos.csv", mime="text/csv")
    matched_csv = matched_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV - Decisões encontradas", data=matched_csv, file_name="decisoes_encontradas.csv", mime="text/csv")
    st.download_button("Download PDF - Relatório", data=pdf_bytes, file_name="relatorio_analise.pdf", mime="application/pdf")

st.markdown('<div class="footer-custom">© 2025 — Nicolly Soares Mota & Maria Eduarda de Bustamante Fontoura — Analisador de Sentenças STF/STJ</div>', unsafe_allow_html=True)
