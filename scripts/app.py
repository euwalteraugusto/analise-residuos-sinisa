"""
MPV - Análise e Diagnóstico da Gestão de Resíduos Sólidos Urbanos (Streamlit).

Fonte: Ministério das Cidades - SINISA 2025 (ano de referência 2024).
Pré-requisito: banco gerado por scripts/etl_sqlite.py (dados_tratados/projeto_residuos.db).

Execução, a partir da raiz do projeto:
    streamlit run scripts/app.py
"""

import os
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="MPV - Resíduos Sólidos", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_BANCO = os.path.normpath(os.path.join(BASE_DIR, "..", "dados_tratados", "projeto_residuos.db"))

INDICADORES = ["IRS0001", "IRS0005", "IRS1004", "IRS3001", "IRS3002", "IRS3010"]
# (código, rótulo curto, sufixo da unidade)
KPIS = [
    ("IRS3002", "Disposição inadequada", "%"),
    ("IRS0001", "Cobertura da coleta", "%"),
    ("IRS1004", "Massa per capita", " kg/hab.dia"),
]
TODO_BRASIL = "Brasil (todas as UFs)"


# -----------------------------------------------------------------------------
# Dados
# -----------------------------------------------------------------------------
@st.cache_data
def carregar_dados(caminho):
    conn = sqlite3.connect(caminho)
    try:
        resultados = pd.read_sql_query(
            """
            SELECT m.cod_ibge, m.nome_municipio, m.uf, m.regiao, m.populacao_total,
                   r.codigo_indicador, r.valor, r.flag_qualidade
            FROM resultado_indicador r
            JOIN municipio m ON m.cod_ibge = r.cod_ibge
            """,
            conn,
        )
        municipios = pd.read_sql_query("SELECT uf, respondeu FROM municipio", conn)
        catalogo = pd.read_sql_query("SELECT codigo, nome, unidade, definicao FROM indicador ORDER BY codigo", conn)
    finally:
        conn.close()
    return resultados, municipios, catalogo


def montar_tabela(resultados, excluir_sinalizados):
    """Uma linha por município e uma coluna por indicador."""
    base = resultados
    if excluir_sinalizados:
        base = base[base["flag_qualidade"].isna()]
    tabela = base.pivot_table(
        index=["cod_ibge", "nome_municipio", "uf", "regiao", "populacao_total"],
        columns="codigo_indicador",
        values="valor",
    ).reset_index()
    tabela.columns.name = None
    return tabela


def resumo_indicador(serie, pesos):
    """Estatísticas de um indicador (média ponderada usa a população como peso)."""
    validos = serie.notna()
    s, p = serie[validos], pesos[validos]
    if s.empty:
        return {"N": 0, "Média": None, "Mediana": None, "Desvio-padrão": None, "Mínimo": None,
                "Máximo": None, "% = 0": None, "% = 100": None, "Média ponderada": None}
    return {
        "N": int(s.count()),
        "Média": s.mean(),
        "Mediana": s.median(),
        "Desvio-padrão": s.std(ddof=1),
        "Mínimo": s.min(),
        "Máximo": s.max(),
        "% = 0": (s == 0).mean() * 100,
        "% = 100": (s == 100).mean() * 100,
        "Média ponderada": float((s * p).sum() / p.sum()),
    }


def ranking_ufs(tabela, indicador="IRS3002"):
    """Média simples e ponderada do indicador por UF, com posições (1 = pior)."""
    base = tabela.dropna(subset=[indicador]).copy()
    base["valor_x_pop"] = base[indicador] * base["populacao_total"]
    por_uf = base.groupby("uf").agg(
        municipios=(indicador, "size"),
        media_simples=(indicador, "mean"),
        soma_valor_pop=("valor_x_pop", "sum"),
        soma_pop=("populacao_total", "sum"),
    )
    por_uf["media_ponderada"] = por_uf["soma_valor_pop"] / por_uf["soma_pop"]
    por_uf["posicao_simples"] = por_uf["media_simples"].rank(method="min", ascending=False).astype(int)
    por_uf["posicao_ponderada"] = por_uf["media_ponderada"].rank(method="min", ascending=False).astype(int)
    return por_uf.drop(columns=["soma_valor_pop", "soma_pop"]).reset_index()


def formatar(valor, casas=2, sufixo=""):
    return "sem dados" if valor is None or pd.isna(valor) else f"{valor:.{casas}f}{sufixo}"


# -----------------------------------------------------------------------------
# Carga com mensagens de erro claras
# -----------------------------------------------------------------------------
if not os.path.exists(CAMINHO_BANCO):
    st.error("Banco de dados não encontrado. Execute primeiro: python scripts/etl_sqlite.py")
    st.stop()

try:
    df_resultados, df_municipios, df_catalogo = carregar_dados(CAMINHO_BANCO)
except (sqlite3.OperationalError, pd.errors.DatabaseError):
    st.error("O banco de dados está desatualizado. Execute novamente: python scripts/etl_sqlite.py")
    st.stop()

nomes = dict(zip(df_catalogo["codigo"], df_catalogo["nome"]))

# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------
st.sidebar.header("Filtros")
ufs_disponiveis = sorted(df_resultados["uf"].unique().tolist())
uf_selecionada = st.sidebar.selectbox("Selecione o Estado (UF)", [TODO_BRASIL] + ufs_disponiveis)
excluir = st.sidebar.checkbox(
    "Excluir valores sinalizados",
    value=False,
    help="Remove dos cálculos os valores marcados como suspeitos no ETL "
         "(percentual acima de 100 e massa per capita muito alta).",
)
st.sidebar.caption("Fonte: Ministério das Cidades - SINISA 2025 (ano de referência 2024).")

tabela_brasil = montar_tabela(df_resultados, excluir)
if uf_selecionada == TODO_BRASIL:
    tabela = tabela_brasil
    municipios_escopo = df_municipios
else:
    tabela = tabela_brasil[tabela_brasil["uf"] == uf_selecionada]
    municipios_escopo = df_municipios[df_municipios["uf"] == uf_selecionada]

# -----------------------------------------------------------------------------
# Cabeçalho
# -----------------------------------------------------------------------------
st.title("♻️ Análise e Diagnóstico da Gestão de Resíduos Sólidos")
st.markdown("Produto Mínimo Viável (MPV) - Dados do SINISA 2025 (ano de referência 2024), municípios respondentes.")

st.header(f"Resultados para: {uf_selecionada}")
n_resp = int(municipios_escopo["respondeu"].sum())
n_total = len(municipios_escopo)
st.caption(f"{n_resp} de {n_total} municípios responderam ao módulo de resíduos ({n_resp / n_total * 100:.1f}%). "
           "Só eles entram na análise.")

# -----------------------------------------------------------------------------
# Indicadores principais
# -----------------------------------------------------------------------------
colunas = st.columns(len(KPIS))
for coluna, (codigo, rotulo, sufixo) in zip(colunas, KPIS):
    r = resumo_indicador(tabela[codigo], tabela["populacao_total"])
    coluna.metric(f"{rotulo} (média simples)", formatar(r["Média"], 2, sufixo),
                  help=f"{codigo} - {nomes[codigo]}")
    coluna.caption(f"Mediana: {formatar(r['Mediana'], 2, sufixo)}  |  "
                   f"Média ponderada por população: {formatar(r['Média ponderada'], 2, sufixo)}")

ranking = ranking_ufs(tabela_brasil)
if uf_selecionada == TODO_BRASIL:
    st.info("A média simples dá o mesmo peso a cada município. A média ponderada considera a população, "
            "por isso as duas podem diferir bastante, principalmente no IRS3002, que se concentra em 0% e 100%.")
else:
    linha = ranking[ranking["uf"] == uf_selecionada]
    if not linha.empty:
        l = linha.iloc[0]
        st.info(f"No ranking de disposição final inadequada (IRS3002; posição 1 = pior), {uf_selecionada} ocupa a "
                f"{int(l['posicao_simples'])}ª posição de {len(ranking)} pela média simples ({l['media_simples']:.2f}%) "
                f"e a {int(l['posicao_ponderada'])}ª pela média ponderada por população ({l['media_ponderada']:.2f}%).")
    if uf_selecionada == "DF":
        st.warning("O DF tem apenas 1 município; interprete os resultados com cautela.")
    if uf_selecionada == "SP":
        st.caption("Contexto do projeto: SP é o estado da empresa analisada no diagnóstico de qualidade, que consta no "
                   "relatório. Os indicadores do SINISA descrevem resíduos urbanos municipais e não avaliam a gestão "
                   "de resíduos de empresas.")

st.divider()

# -----------------------------------------------------------------------------
# Resumo estatístico
# -----------------------------------------------------------------------------
st.subheader("Resumo estatístico dos indicadores")
linhas = []
for codigo in INDICADORES:
    r = resumo_indicador(tabela[codigo], tabela["populacao_total"])
    linhas.append({"Código": codigo, "Indicador": nomes[codigo], **r})
df_resumo = pd.DataFrame(linhas).round(2)
st.dataframe(df_resumo, hide_index=True)

# -----------------------------------------------------------------------------
# Distribuição de um indicador
# -----------------------------------------------------------------------------
st.subheader("Distribuição de um indicador")
indicador_dist = st.selectbox("Indicador", INDICADORES, index=INDICADORES.index("IRS3002"),
                              format_func=lambda c: f"{c} - {nomes[c]}")
serie = tabela[indicador_dist].dropna()
if serie.empty:
    st.write("Sem dados para exibir.")
else:
    histograma = (
        alt.Chart(pd.DataFrame({"valor": serie}))
        .mark_bar()
        .encode(
            x=alt.X("valor:Q", bin=alt.Bin(maxbins=20), title="Valor do indicador"),
            y=alt.Y("count()", title="Número de municípios"),
        )
        .properties(height=280, width="container")
    )
    st.altair_chart(histograma)
    st.caption(f"{(serie == 0).mean() * 100:.1f}% dos municípios têm valor 0 e "
               f"{(serie == 100).mean() * 100:.1f}% têm valor 100. Distribuições concentradas nos extremos "
               "tornam a média pouco representativa; observe também a mediana.")

# -----------------------------------------------------------------------------
# Ranking das UFs
# -----------------------------------------------------------------------------
st.subheader("Ranking das UFs - disposição final inadequada (IRS3002)")
ordem = ranking.sort_values("media_simples", ascending=False)["uf"].tolist()
longo = ranking.melt(id_vars=["uf"], value_vars=["media_simples", "media_ponderada"],
                     var_name="medida", value_name="valor")
longo["medida"] = longo["medida"].map({"media_simples": "Média simples", "media_ponderada": "Média ponderada"})
destaque = alt.condition(alt.datum.uf == uf_selecionada, alt.value(1.0), alt.value(0.45))
grafico = (
    alt.Chart(longo)
    .mark_bar()
    .encode(
        x=alt.X("uf:N", sort=ordem, title="UF"),
        y=alt.Y("valor:Q", title="% em disposição inadequada"),
        color=alt.Color("medida:N", title="Medida"),
        xOffset="medida:N",
        opacity=destaque if uf_selecionada != TODO_BRASIL else alt.value(1.0),
        tooltip=["uf", "medida", alt.Tooltip("valor:Q", format=".2f")],
    )
    .properties(height=320, width="container")
)
st.altair_chart(grafico)
st.caption("Barras em ordem decrescente da média simples (pior cenário à esquerda). "
           "A UF selecionada fica em destaque.")

# -----------------------------------------------------------------------------
# Tabela de municípios
# -----------------------------------------------------------------------------
st.subheader("Visualização dos Municípios")
df_municipios_tabela = tabela.drop(columns=["cod_ibge", "regiao"]).rename(
    columns={"nome_municipio": "município", "populacao_total": "população"})
st.dataframe(df_municipios_tabela, hide_index=True)
st.download_button(
    "Baixar tabela (CSV)",
    data=df_municipios_tabela.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"municipios_{'brasil' if uf_selecionada == TODO_BRASIL else uf_selecionada}.csv",
    mime="text/csv",
)

st.divider()

# -----------------------------------------------------------------------------
# Metodologia e limitações
# -----------------------------------------------------------------------------
with st.expander("Metodologia, definições e limitações"):
    st.markdown(
        "- **Fonte:** Ministério das Cidades, SINISA 2024 (ano de referência 2023), planilha de indicadores de "
        "resíduos sólidos urbanos.\n"
        f"- **Cobertura:** {int(df_municipios['respondeu'].sum())} de {len(df_municipios)} municípios do país "
        f"responderam ao módulo ({df_municipios['respondeu'].mean() * 100:.1f}%). Os demais ficam fora da análise.\n"
        "- **Média ponderada:** usa a população total do município como peso.\n"
        "- **Valores sinalizados:** percentuais acima de 100 e massa per capita acima de 3 kg/hab.dia são "
        "marcados no ETL e mantidos por padrão; use o filtro lateral para excluí-los.\n"
        "- **Zeros:** o valor 0 pode indicar ausência do serviço ou do envio da informação; consulte o glossário do SINISA.\n"
        "- **Escopo:** os indicadores tratam de resíduos sólidos urbanos municipais, não de resíduos industriais "
        "nem da gestão ambiental de empresas.\n"
        "- **Associação não é causalidade:** os resultados descrevem os dados e não explicam suas causas."
    )
    st.markdown("**Definição dos indicadores**")
    st.dataframe(
        df_catalogo.rename(columns={"codigo": "Código", "nome": "Nome", "unidade": "Unidade", "definicao": "Definição"}),
        hide_index=True,
    )