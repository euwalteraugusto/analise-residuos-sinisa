# ♻️ MPV - Análise e Diagnóstico da Gestão de Resíduos Sólidos

Projeto interdisciplinar de extensão universitária desenvolvido para organizar, analisar e apresentar dados públicos sobre a gestão de resíduos sólidos (SINISA 2024), integrando estatística, banco de dados e engenharia de software com um diagnóstico ambiental prático.

## 🎯 Objetivos do Projeto
- **Banco de Dados:** Modelagem relacional e estruturação de dados em SQLite a partir de um processo de ETL (Extração, Transformação e Carga).
- **Estatística:** Análise descritiva de indicadores ambientais e geração de rankings estaduais.
- **Gestão da Qualidade:** Aplicação de ferramentas (PDCA, 5W2H, Ishikawa) para propor melhorias operacionais e ambientais na empresa CGA Equipamentos Contra Incêndio LTDA.
- **Programação II:** Desenvolvimento de um dashboard interativo utilizando Python e Streamlit.

## 🛠️ Tecnologias Utilizadas
- **Python 3.x** (Lógica, ETL e Backend)
- **Pandas** (Tratamento de Dados e Estatística)
- **SQLite3** (Banco de Dados Relacional embutido)
- **Streamlit** (Criação do Dashboard Web - MPV)

## 📂 Estrutura do Repositório
```text
📦 Projeto_Extensao_FATEC
 ┣ 📂 dados_originais     # Planilhas brutas baixadas do SINISA
 ┣ 📂 dados_tratados      # Banco SQLite gerado (projeto_residuos.db)
 ┣ 📂 scripts
 ┃ ┣ 📜 etl_sqlite.py           # Script responsável pelo ETL e criação do DB
 ┃ ┣ 📜 analise_estatistica.py  # Script de processamento das métricas
 ┃ ┗ 📜 app.py                  # Dashboard Web (Streamlit)
 ┣ 📜 Projeto_Final.docx  # Relatório acadêmico consolidado
 ┗ 📜 README.md

 👥 Autores
Gabriel Champin

Gabriel Kenji

Luana Monteiro

Pedro Genaro

Walter Augusto

Faculdade de Tecnologia de São Bernardo do Campo "Adib Moisés Dib"