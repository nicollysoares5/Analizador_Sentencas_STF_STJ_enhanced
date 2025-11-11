# Analisador de Sentenças do STF/STJ (Versão 3)

Aplicativo Streamlit para busca e análise de ementas de decisões dos tribunais superiores (STF / STJ).
Inclui: buscador com filtros, cards de resultados, painel analítico, nuvem de palavras e exportação de relatórios (CSV / PDF).

## Arquivos principais
- `app.py` — aplicação Streamlit.
- `requirements.txt` — dependências.
- (opcional) `decisoes_stf_stj.csv` — CSV com decisões.

## Como usar (sem terminal)
1. No GitHub: crie um repositório (por exemplo `analisador-sentencas-stf-stj`).
2. Clique em **Add file → Upload files** e envie `app.py`, `requirements.txt` e `README.md`.
3. Acesse [https://share.streamlit.io](https://share.streamlit.io), clique em **New app**, selecione seu repositório, branch `main` e o arquivo `app.py`. Clique em **Deploy**.
4. Pronto — seu app estará publicado com URL do Streamlit Cloud.

## Como usar localmente (opcional)
1. Baixe/clone o repositório.
2. (Recomendado) crie e ative um virtualenv:
   - macOS/Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - Windows (PowerShell):
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
3. Instale dependências:
   ```bash
   pip install -r requirements.txt

