# Analisador de Sentenças do STF/STJ

Versão aprimorada do app Streamlit com visual, nuvem de palavras e exportação de PDF.

## Como usar (local)

1. Descompacte o ZIP e entre na pasta do projeto.
2. (Opcional) Crie um ambiente virtual (recomendado):
   - macOS / Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - Windows (PowerShell):
     ```powershell
     python -m venv venv
     .\\venv\\Scripts\\Activate.ps1
     ```

3. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Rode:
   ```bash
   streamlit run app.py
   ```

## Deploy no Streamlit Cloud (sem terminal)

1. Crie um repositório no GitHub.
2. Faça upload dos arquivos **app.py**, **requirements.txt** e **README.md** pelo botão _Add file > Upload files_.
3. No Streamlit Cloud, clique em **New app**, selecione seu repositório, branch `main` e `app.py` como o arquivo principal e clique em **Deploy**.
