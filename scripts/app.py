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
    ("IRS1004", "Massa per capita (kg/hab.dia)", ""),
]
# Nomes curtos para tabelas (o nome oficial completo fica na dica e na aba Método)
CURTOS = {"IRS0001": "Cobertura da coleta (%)", "IRS0005": "Coleta seletiva (%)", "IRS1004": "Massa per capita (kg/hab.dia)",
          "IRS3001": "Desempenho da coleta seletiva (%)", "IRS3002": "Disposição inadequada (%)",
          "IRS3010": "Recuperação de recicláveis (%)"}
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
    """Número no padrão brasileiro (vírgula decimal, ponto de milhar)."""
    if valor is None or pd.isna(valor):
        return "sem dados"
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto + sufixo


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
# Estilo
# -----------------------------------------------------------------------------
COR_PRINCIPAL = "#1F5E4B"   # verde: padrão
COR_DESTAQUE = "#B5451B"    # ferrugem: UF selecionada / alerta
COR_NEUTRA = "#B9B4A6"      # cinza quente: demais UFs
COR_TEXTO = "#1F2A24"

st.markdown(
    """
    <style>
    .block-container {padding-top: 4rem; max-width: 1180px;}
    .kicker {font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; color: #6B6F66; margin-bottom: 0.2rem;}
    .lede {font-family: serif; font-size: 1.35rem; line-height: 1.45; margin: 0.4rem 0 1.4rem 0; max-width: 62rem;}
    div[data-testid="stMetricValue"] {font-family: serif;}
    @media (max-width: 640px) {
        .block-container {padding-top: 3rem;}
        h1 {font-size: 2rem !important; line-height: 1.15 !important;}
        .lede {font-size: 1.1rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def estilizar(grafico):
    return (
        grafico.configure_view(stroke=None)
        .configure_axis(grid=False, domainColor="#8A8F98", tickColor="#8A8F98", labelColor=COR_TEXTO,
                        titleColor="#6B6F66", labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
        .configure_axisY(grid=True, gridColor="#E3DFD3")
    )


# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------
st.sidebar.header("Recorte")
ufs_disponiveis = sorted(df_resultados["uf"].unique().tolist())
uf_selecionada = st.sidebar.selectbox("Estado (UF)", [TODO_BRASIL] + ufs_disponiveis)
excluir = st.sidebar.checkbox(
    "Excluir valores suspeitos",
    value=False,
    help="Remove dos cálculos os valores marcados no ETL (percentual acima de 100 e massa per capita acima de 3 kg/hab.dia).",
)
st.sidebar.caption("Fonte: Ministério das Cidades, SINISA 2025 (ano de referência 2024). Só entram municípios que responderam ao módulo de resíduos.")

tabela_brasil = montar_tabela(df_resultados, excluir)
if uf_selecionada == TODO_BRASIL:
    tabela = tabela_brasil
    municipios_escopo = df_municipios
else:
    tabela = tabela_brasil[tabela_brasil["uf"] == uf_selecionada]
    municipios_escopo = df_municipios[df_municipios["uf"] == uf_selecionada]

n_resp = int(municipios_escopo["respondeu"].sum())
n_total = len(municipios_escopo)
resumo_br = {c: resumo_indicador(tabela_brasil[c], tabela_brasil["populacao_total"]) for c in INDICADORES}
resumo_uf = {c: resumo_indicador(tabela[c], tabela["populacao_total"]) for c in INDICADORES}
ranking = ranking_ufs(tabela_brasil)

# -----------------------------------------------------------------------------
# Cabeçalho
# -----------------------------------------------------------------------------
st.markdown('<div class="kicker">Projeto de extensão · FATEC São Bernardo do Campo · SINISA 2025 (dados de 2024)</div>',
            unsafe_allow_html=True)
st.title("Para onde vão os resíduos dos municípios brasileiros?")

m3002 = resumo_uf["IRS3002"]
if uf_selecionada == TODO_BRASIL:
    lede = (f"Nos {formatar(n_resp, 0)} municípios que responderam, em média {formatar(m3002['Média'], 1, '%')} dos resíduos coletados "
            f"vão para lixão, vazadouro ou aterro controlado. Ponderando pela população, a parcela cai para "
            f"{formatar(m3002['Média ponderada'], 1, '%')}: os municípios pequenos puxam a média para cima.")
else:
    linha = ranking[ranking["uf"] == uf_selecionada]
    pos = f" ({int(linha.iloc[0]['posicao_simples'])}ª pior entre {len(ranking)} UFs)" if not linha.empty else ""
    lede = (f"Em {uf_selecionada}, em média {formatar(m3002['Média'], 1, '%')} dos resíduos vão para lixão, vazadouro ou aterro "
            f"controlado{pos}, contra {formatar(resumo_br['IRS3002']['Média'], 1, '%')} no Brasil. "
            f"Ponderando pela população, {formatar(m3002['Média ponderada'], 1, '%')}.")
st.markdown(f'<p class="lede">{lede}</p>', unsafe_allow_html=True)
st.caption(f"{formatar(n_resp, 0)} de {formatar(n_total, 0)} municípios do recorte responderam ao módulo de resíduos ({formatar(n_resp / n_total * 100, 1)}%).")

colunas = st.columns(len(KPIS))
for coluna, (codigo, rotulo, sufixo) in zip(colunas, KPIS):
    r = resumo_uf[codigo]
    base = resumo_br[codigo]["Média"]
    delta = None
    if uf_selecionada != TODO_BRASIL and r["Média"] is not None and not pd.isna(r["Média"]):
        delta = f"{r['Média'] - base:+.2f} vs. Brasil".replace(".", ",")
    coluna.metric(rotulo, formatar(r["Média"], 2, sufixo), delta,
                  delta_color="inverse" if codigo == "IRS3002" else ("off" if codigo == "IRS1004" else "normal"),
                  help=f"{codigo} - {nomes[codigo]}. Média simples dos municípios.")
    coluna.caption(f"Mediana {formatar(r['Mediana'], 2, sufixo)} · ponderada por população {formatar(r['Média ponderada'], 2, sufixo)}")

st.write("")
aba_panorama, aba_ranking, aba_municipios, aba_metodo = st.tabs(["Panorama", "Ranking das UFs", "Municípios", "Método e limitações"])

# -----------------------------------------------------------------------------
# Panorama
# -----------------------------------------------------------------------------
with aba_panorama:
    st.subheader("Distribuição de um indicador")
    indicador_dist = st.selectbox("Indicador", INDICADORES, index=INDICADORES.index("IRS3002"),
                                  format_func=lambda c: f"{c} · {nomes[c]}")
    serie = tabela[indicador_dist].dropna()
    if serie.empty:
        st.write("Sem dados para exibir.")
    else:
        mediana = float(serie.median())
        dados_hist = pd.DataFrame({"valor": serie})
        barras = (
            alt.Chart(dados_hist)
            .mark_bar(color=COR_NEUTRA)
            .encode(
                x=alt.X("valor:Q", bin=alt.Bin(maxbins=20), title="Valor do indicador"),
                y=alt.Y("count()", title="Municípios"),
            )
        )
        linha_med = alt.Chart(pd.DataFrame({"m": [mediana]})).mark_rule(color=COR_DESTAQUE, strokeWidth=2).encode(x="m:Q")
        rotulo_med = (
            alt.Chart(pd.DataFrame({"m": [mediana], "t": [f"mediana {formatar(mediana, 1)}"]}))
            .mark_text(align="left", dx=6, dy=-4, color=COR_DESTAQUE, fontSize=12, baseline="top")
            .encode(x="m:Q", y=alt.value(0), text="t:N")
        )
        st.altair_chart(estilizar((barras + linha_med + rotulo_med).properties(height=300)))
        st.caption(f"{formatar((serie == 0).mean() * 100, 1)}% dos municípios têm valor 0 e {formatar((serie == 100).mean() * 100, 1)}% têm valor 100. "
                   "Quando os valores se concentram nos extremos, a média representa pouco; compare com a mediana.")

    st.subheader("Resumo estatístico")
    linhas = [{"Indicador": CURTOS[c], **resumo_uf[c]} for c in INDICADORES]
    st.dataframe(pd.DataFrame(linhas).round(2), hide_index=True,
                 column_config={col: st.column_config.NumberColumn(col, format="localized")
                                for col in resumo_uf[INDICADORES[0]]})
    if uf_selecionada == "DF":
        st.caption("O DF tem apenas 1 município; interprete os resultados com cautela.")
    if uf_selecionada == "SP":
        st.caption("SP é o estado da empresa analisada no diagnóstico de qualidade do relatório. Os indicadores do SINISA "
                   "descrevem resíduos urbanos municipais e não avaliam a gestão de resíduos de empresas.")

# -----------------------------------------------------------------------------
# Ranking
# -----------------------------------------------------------------------------
with aba_ranking:
    st.subheader("Disposição final inadequada por UF (IRS3002)")
    medida = st.radio("Medida", ["Média simples", "Média ponderada por população"], horizontal=True,
                      help="A simples dá o mesmo peso a cada município; a ponderada usa a população.")
    coluna_medida = "media_simples" if medida == "Média simples" else "media_ponderada"
    dados_rank = ranking[["uf", coluna_medida]].rename(columns={coluna_medida: "valor"}).sort_values("valor", ascending=False)
    if uf_selecionada == TODO_BRASIL:
        cor = alt.value(COR_PRINCIPAL)
    else:
        cor = alt.condition(alt.datum.uf == uf_selecionada, alt.value(COR_DESTAQUE), alt.value(COR_NEUTRA))
    dados_rank["rotulo"] = dados_rank["valor"].map(lambda v: formatar(v, 1))
    base_rank = alt.Chart(dados_rank).encode(
        y=alt.Y("uf:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False, labelPadding=6)),
        x=alt.X("valor:Q", title="% em disposição inadequada"))
    barras_rank = base_rank.mark_bar().encode(color=cor, tooltip=["uf", alt.Tooltip("rotulo:N", title="valor (%)")])
    textos = base_rank.mark_text(align="left", dx=4, fontSize=11, color=COR_TEXTO).encode(text="rotulo:N")
    st.altair_chart(estilizar((barras_rank + textos).properties(height=27 * 20)))
    st.caption("Do pior para o melhor. A UF selecionada aparece em destaque. As duas medidas podem divergir bastante porque o IRS3002 "
               "se concentra em 0% e 100%.")

# -----------------------------------------------------------------------------
# Municípios
# -----------------------------------------------------------------------------
with aba_municipios:
    st.subheader("Municípios")
    df_municipios_tabela = tabela.drop(columns=["cod_ibge", "regiao"]).rename(
        columns={"nome_municipio": "município", "populacao_total": "população"})
    unidades = {"IRS1004": "kg/hab.dia"}
    config_colunas = {
        "município": st.column_config.TextColumn("Município", pinned=True),
        "uf": st.column_config.TextColumn("UF", width="small"),
        "população": st.column_config.NumberColumn("População", format="localized"),
    }
    for c in INDICADORES:
        config_colunas[c] = st.column_config.NumberColumn(
            CURTOS[c], help=f"{c}: {nomes[c]} ({unidades.get(c, '%')})", format="localized", width="medium")
    st.caption("Passe o mouse sobre o título da coluna para ver o código e a definição do indicador. Clique no título para ordenar.")
    tabela_exibida = df_municipios_tabela.copy()
    tabela_exibida[INDICADORES] = tabela_exibida[INDICADORES].round(2)
    st.dataframe(tabela_exibida, hide_index=True, column_config=config_colunas)
    st.download_button(
        "Baixar tabela (CSV)",
        data=df_municipios_tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"municipios_{'brasil' if uf_selecionada == TODO_BRASIL else uf_selecionada}.csv",
        mime="text/csv",
    )

# -----------------------------------------------------------------------------
# Metodologia e limitações
# -----------------------------------------------------------------------------
with aba_metodo:
    st.markdown(
        "- **Fonte:** Ministério das Cidades, SINISA 2025 (ano de referência 2024), planilha de indicadores de "
        "resíduos sólidos urbanos.\n"
        f"- **Cobertura:** {int(df_municipios['respondeu'].sum())} de {len(df_municipios)} municípios do país "
        f"responderam ao módulo ({formatar(df_municipios['respondeu'].mean() * 100, 1)}%). Os demais ficam fora da análise.\n"
        "- **Média ponderada:** usa a população total do município como peso.\n"
        "- **Valores suspeitos:** percentuais acima de 100 e massa per capita acima de 3 kg/hab.dia são "
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
