import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
from io import BytesIO
from fpdf import FPDF
import os
from collections import Counter

# ---------------- CONFIGURAÇÃO DA PÁGINA ----------------
st.set_page_config(
    page_title='Analisador de Sentenças STF/STJ',
    layout='wide',
    initial_sidebar_state='expanded'
)

# ---------------- ESTILO PERSONALIZADO ----------------
st.markdown("""
<style>
.reportview-container {
    background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
}
.sidebar .sidebar-content {
    background: linear-gradient(#e6f0ff, #ffffff);
}
.big-font {
    font-size:28px !important;
    font-weight:700;
}
.small-muted {
    color: #6b7280;
    font-size:12px;
}
footer {visibility: hidden;}
.custom-footer {
    padding: 12px 0;
    color: #0b3d91;
    text-align: center;
    font-size: 13px;
}
.card {
    background: white;
    padding: 12px;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(12, 35, 60, 0.08);
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-font">🧾 Analisador de Sentenças do STF / STJ</div>', unsafe_allow_html=True)
st.markdown('<div class="small-muted">Ferramenta para análise de termos em ementas e visualização de padrões decisórios.</div>', unsafe_allow_html=True)
st.markdown("---")

# ---------------- BARRA LATERAL ----------------
with st.sidebar:
    st.header("Upload de dados")
    uploaded = st.file_uploader("Carregar CSV (colunas: ID_Decisao, Tribunal, Ementa, Resultado, Data)", type=['csv'])
    st.markdown("**Exemplo**: `decisoes_stf_stj.csv` com cabeçalhos corretos.")
    st.markdown("---")
    st.header("Filtros / Análise")
    tribunal_choice = st.selectbox("Filtrar por Tribunal", ["Ambos", "STF", "STJ"], index=0)
    keywords_input = st.text_input("Termos-chave (separados por vírgula)", value="dano moral, repercussão geral, inconstitucionalidade")
    extra_stopwords = st.text_area("Stopwords adicionais (uma por linha) — para a nuvem de palavras", value="de\na\no\nem\npara\ncom\npor\nque")
    run_btn = st.button("Rodar Análise")
    st.markdown("---")
    st.markdown("**Exportar / Deploy**")
    st.markdown("Depois de enviar para o GitHub, conecte o repositório ao Streamlit Cloud para deploy automático.")

# ---------------- FUNÇÕES AUXILIARES ----------------
def generate_sample_df(n=30):
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
        'Tutela antecipada concedida; parcialmente procedente',
        'Recurso especial improvido; não há violação federal'
    ]
    resultados = ['Procedente','Improcedente','Parcialmente Procedente']
    tribunais = ['STF','STJ']
    data = []
    for i in range(1, n+1):
        data.append({
            'ID_Decisao': i,
            'Tribunal': random.choice(tribunais),
            'Ementa': random.choice(sample_ementas),
            'Resultado': random.choice(resultados),
            'Data': f"202{random.randint(0,4)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        })
    return pd.DataFrame(data)

def load_csv(uploaded_file):
    if uploaded_file is not None:
        try:
            return pd.read_csv(uploaded_file)
        except Exception:
            uploaded_file.seek(0)
            try:
                return pd.read_csv(uploaded_file, encoding='utf-8-sig')
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding='latin1')
    else:
        fallback = "decisoes_stf_stj.csv"
        if os.path.exists(fallback):
            try:
                return pd.read_csv(fallback)
            except Exception:
                return pd.read_csv(fallback, encoding='latin1')
        else:
            return generate_sample_df()

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

def make_wordcloud(text_series, extra_sw=None):
    text = " ".join(text_series.fillna('').astype(str).tolist()).lower()
    stopwords = set(STOPWORDS)
    if extra_sw:
        for s in extra_sw:
            stopwords.add(s.strip().lower())
    wc = WordCloud(width=800, height=400, background_color='white', stopwords=stopwords, collocations=False).generate(text)
    return wc

def create_pdf_report(freq_df, matched_df, fig_res_bytes, fig_trib_bytes, wc_bytes):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "Relatório de Análise - Analisador de Sentenças STF/STJ", ln=True)
    pdf.cell(0, 6, "", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, "Autores: Nicolly Soares Mota; Maria Eduarda de Bustamante Fontoura", ln=True)
    pdf.cell(0, 6, "", ln=True)

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, "Frequência de termos:", ln=True)
    pdf.ln(2)
    for idx, row in freq_df.iterrows():
        pdf.cell(0, 6, f"{row['Termo']}: {row['Contagem']}", ln=True)
    pdf.ln(4)

    for img_bytes, title in [(fig_res_bytes, "Distribuição de Resultados"), (fig_trib_bytes, "Distribuição por Tribunal"), (wc_bytes, "Nuvem de Palavras")]:
        if img_bytes is None:
            continue
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 6, title, ln=True)
        fname = "temp_img.png"
        with open(fname, "wb") as f:
            f.write(img_bytes)
        pdf.image(fname, w=170)
        os.remove(fname)
        pdf.ln(4)

    out = BytesIO()
    out.write(pdf.output(dest='S').encode('latin-1'))
    out.seek(0)
    return out.getvalue()

# ---------------- CARREGAR E VALIDAR DADOS ----------------
df = load_csv(uploaded)
required = {'ID_Decisao','Tribunal','Ementa','Resultado'}
if not required.issubset(set(df.columns)):
    st.error(f"CSV precisa conter colunas: {required}. Colunas encontradas: {list(df.columns)}")
    st.stop()

st.markdown("### 🔎 Configuração da Análise")
col1, col2 = st.columns([2,1])
with col1:
    st.write(f"Decisões carregadas: **{len(df)}**")
    if 'Data' in df.columns:
        st.write(f"Ano - intervalo: {pd.to_datetime(df['Data'], errors='coerce').min()} até {pd.to_datetime(df['Data'], errors='coerce').max()}")
with col2:
    st.write("Filtros aplicados:")
    st.write(f"Tribunal: **{tribunal_choice}**")

st.markdown("---")

# ---------------- EXECUTAR ANÁLISE ----------------
df_proc = df.copy()
if tribunal_choice != 'Ambos':
    df_proc = df_proc[df_proc['Tribunal'].str.upper() == tribunal_choice.upper()].copy()

if run_btn or st.session_state.get('last_run') is None:
    st.session_state['last_run'] = True

    keywords = [k.strip().lower() for k in keywords_input.split(',') if k.strip()]
    extra_sw = [s.strip().lower() for s in extra_stopwords.splitlines() if s.strip()]

    if not keywords:
        st.warning("Insira ao menos um termo-chave na barra lateral.")
    else:
        counts, mask = count_keywords(df_proc, 'Ementa', keywords)
        freq_df = pd.DataFrame.from_dict(counts, orient='index', columns=['Contagem']).reset_index().rename(columns={'index':'Termo'})
        matched_df = df_proc.loc[mask, ['ID_Decisao','Tribunal','Resultado','Ementa','Data']].copy() if 'Data' in df_proc.columns else df_proc.loc[mask, ['ID_Decisao','Tribunal','Resultado','Ementa']].copy()

        # Frequência de termos
        st.subheader("📈 Frequência de termos")
        st.table(freq_df)

        # Gráficos
        st.subheader("📊 Gráficos de Distribuição")
        res_counts = df_proc['Resultado'].value_counts().reset_index()
        res_counts.columns = ['Resultado','Quantidade']
        fig_res = px.bar(res_counts, x='Resultado', y='Quantidade', title='Distribuição de Resultados', text='Quantidade')
        fig_res.update_layout(title=dict(x=0.5), plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_res, use_container_width=True)

        trib_counts = df_proc['Tribunal'].value_counts().reset_index()
        trib_counts.columns = ['Tribunal','Quantidade']
        fig_trib = px.pie(trib_counts, names='Tribunal', values='Quantidade', title='Proporção por Tribunal')
        st.plotly_chart(fig_trib, use_container_width=True)

        # Nuvem de palavras
        st.subheader("☁️ Nuvem de Palavras")
        wc = WordCloud(width=800, height=400, background_color='white',
                       stopwords=set(STOPWORDS).union(extra_sw)).generate(" ".join(df_proc['Ementa']))
        fig_wc, ax = plt.subplots(figsize=(10,4))
        ax.imshow(wc, interpolation='bilinear')
        ax.axis('off')
        st.pyplot(fig_wc)

        # Ranking de palavras
        st.subheader("🏆 Ranking de Palavras (Top 20)")
        all_text = " ".join(df_proc['Ementa'].fillna('').astype(str).tolist()).lower()
        words = [w for w in all_text.split() if len(w)>3 and w.isalpha() and w not in set(extra_sw)]
        top = pd.DataFrame(Counter(words).most_common(20), columns=['Palavra','Frequência'])
        st.table(top)

        # Exportar relatórios
        st.markdown("---")
        st.subheader("📂 Exportar Relatórios")

        csv_bytes = matched_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download - CSV das decisões encontradas", data=csv_bytes, file_name="relatorio_decisoes_encontradas.csv", mime="text/csv")

        freq_csv = freq_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download - Tabela de frequência", data=freq_csv, file_name="tabela_frequencia_termos.csv", mime="text/csv")

        # PDF
        buf_wc = BytesIO(); fig_wc.savefig(buf_wc, format='png', bbox_inches='tight'); buf_wc.seek(0); wc_bytes = buf_wc.read()
        pdf_bytes = create_pdf_report(freq_df, matched_df, fig_res.to_image(format='png'), fig_trib.to_image(format='png'), wc_bytes)
        st.download_button("Download - Relatório em PDF", data=pdf_bytes, file_name="relatorio_analise.pdf", mime="application/pdf")

# Rodapé
st.markdown("<div class='custom-footer'>© 2025 — Nicolly Soares Mota & Maria Eduarda de Bustamante Fontoura — Analisador de Sentenças STF/STJ</div>", unsafe_allow_html=True)
