"""
Gera a planilha de análise estatística (Excel) a partir do banco SQLite.

A aba "Dados" recebe os valores do banco (um município por linha). As demais
abas usam FÓRMULAS do Excel ligadas a ela, então a planilha recalcula sozinha
quando os dados ou os parâmetros mudam. Só a aba "Testes_Python" contém valores
fixos (testes calculados em Python/scipy).

Uso, a partir da raiz do projeto (depois de rodar o ETL):
    python scripts/gerar_planilha.py

Saída: resultados/Analise_Estatistica_Residuos.xlsx
Observação: o Excel calcula as fórmulas ao abrir o arquivo. Visualizadores que
não calculam (por exemplo, a prévia do GitHub) mostram as células vazias; para
publicar uma versão com valores já calculados, abra e salve o arquivo no Excel.

Dependências: pandas, scipy, openpyxl.
"""

import os
import sqlite3

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.formula import ArrayFormula

import analise_estatistica as an

CAMINHO_SAIDA = os.path.join(an.BASE_DIR, "resultados", "Analise_Estatistica_Residuos.xlsx")

# -----------------------------------------------------------------------------
# Estilos
# -----------------------------------------------------------------------------
FONTE = "Arial"
F_TITULO = Font(name=FONTE, size=14, bold=True, color="1F3864")
F_SUBTITULO = Font(name=FONTE, size=10, italic=True, color="595959")
F_NORMAL = Font(name=FONTE, size=10)
F_NEGRITO = Font(name=FONTE, size=10, bold=True)
F_CABECALHO = Font(name=FONTE, size=10, bold=True, color="FFFFFF")
F_ENTRADA = Font(name=FONTE, size=10, color="0000FF")        # valor digitado/importado
F_NOTA = Font(name=FONTE, size=9, italic=True, color="595959")
FILL_CABECALHO = PatternFill("solid", fgColor="1F3864")
FILL_EDITAVEL = PatternFill("solid", fgColor="FFFF00")       # célula para o usuário alterar
FILL_DESTAQUE = PatternFill("solid", fgColor="FFF2CC")
BORDA = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
CENTRO = Alignment(horizontal="center", vertical="center", wrap_text=True)
ESQUERDA = Alignment(horizontal="left", vertical="center", wrap_text=True)

# Colunas da aba Dados
COL = {"cod": "A", "mun": "B", "uf": "C", "reg": "D", "pop": "E",
       "IRS0001": "F", "IRS0005": "G", "IRS1004": "H", "IRS3001": "I", "IRS3002": "J", "IRS3010": "K",
       "sinal_3001": "L", "sinal_1004": "M"}

FMT_2 = "0.00"
FMT_PCT = "0.0%"
FMT_INT = "#,##0"


def escrever(ws, ref, valor, fonte=F_NORMAL, formato=None, alinhamento=None, borda=False, preenchimento=None):
    c = ws[ref]
    c.value = valor
    c.font = fonte
    if formato:
        c.number_format = formato
    if alinhamento:
        c.alignment = alinhamento
    elif borda:
        c.alignment = Alignment(vertical="center")
    if borda:
        c.border = BORDA
    if preenchimento:
        c.fill = preenchimento
    return c


def cabecalho(ws, linha, titulos, coluna_inicial=1):
    for i, texto in enumerate(titulos):
        c = ws.cell(row=linha, column=coluna_inicial + i, value=texto)
        c.font, c.fill, c.alignment, c.border = F_CABECALHO, FILL_CABECALHO, CENTRO, BORDA
    ws.row_dimensions[linha].height = 42


def titulo(ws, texto, subtitulo=None):
    escrever(ws, "A1", texto, F_TITULO)
    if subtitulo:
        escrever(ws, "A2", subtitulo, F_SUBTITULO)
    ws.sheet_view.showGridLines = False


def larguras(ws, mapa):
    for coluna, largura in mapa.items():
        ws.column_dimensions[coluna].width = largura


def nota(ws, ref, texto):
    escrever(ws, ref, texto, F_NOTA, alinhamento=Alignment(wrap_text=False, vertical="top"))


# -----------------------------------------------------------------------------
# Construção da planilha
# -----------------------------------------------------------------------------
def montar(df, catalogo, totais_uf):
    n = len(df)
    ultima = n + 1                                   # última linha de dados na aba Dados

    def rng(chave):
        c = COL[chave]
        return f"Dados!${c}$2:${c}${ultima}"

    ufs = rng("uf")
    pop = rng("pop")

    wb = Workbook()
    ws_leia = wb.active
    ws_leia.title = "Leia-me"
    ws_par = wb.create_sheet("Parametros")
    ws_desc = wb.create_sheet("Descritiva")
    ws_rank = wb.create_sheet("Ranking_UF")
    ws_reg = wb.create_sheet("Regioes")
    ws_painel = wb.create_sheet("Painel_UF")
    ws_assoc = wb.create_sheet("Associacoes")
    ws_py = wb.create_sheet("Testes_Python")
    ws_qual = wb.create_sheet("Qualidade_Dados")
    ws_dados = wb.create_sheet("Dados")

    nomes = dict(zip(catalogo["codigo"], catalogo["nome"]))
    unidades = dict(zip(catalogo["codigo"], catalogo["unidade"]))

    # ---------------------------------------------------------------- Dados
    cab = ["cod_ibge", "Município", "UF", "Região", "População total",
           "IRS0001", "IRS0005", "IRS1004", "IRS3001", "IRS3002", "IRS3010",
           "IRS3001 acima do limite (1 = sim)", "IRS1004 acima do limite (1 = sim)"]
    cabecalho(ws_dados, 1, cab)
    for i, linha in enumerate(df.itertuples(index=False), start=2):
        valores = [str(linha.cod_ibge), linha.nome_municipio, linha.uf, linha.regiao, int(linha.populacao_total),
                   linha.IRS0001, linha.IRS0005, linha.IRS1004, linha.IRS3001, linha.IRS3002, linha.IRS3010]
        for j, v in enumerate(valores, start=1):
            c = ws_dados.cell(row=i, column=j, value=v)
            c.font = F_NORMAL
        ws_dados.cell(row=i, column=5).number_format = FMT_INT
        for j in range(6, 12):
            ws_dados.cell(row=i, column=j).number_format = FMT_2
        f1 = ws_dados.cell(row=i, column=12, value=f"=IF(I{i}>Parametros!$B$3,1,0)")
        f2 = ws_dados.cell(row=i, column=13, value=f"=IF(H{i}>Parametros!$B$4,1,0)")
        f1.font = f2.font = F_NORMAL
    larguras(ws_dados, {"A": 11, "B": 34, "C": 6, "D": 14, "E": 14, "F": 10, "G": 10, "H": 10,
                        "I": 10, "J": 10, "K": 10, "L": 18, "M": 18})
    ws_dados.freeze_panes = "C2"
    ws_dados.auto_filter.ref = f"A1:M{ultima}"

    # ----------------------------------------------------------- Parametros
    titulo(ws_par, "Parâmetros", "Células amarelas podem ser alteradas; as abas de análise recalculam.")
    escrever(ws_par, "A3", "Valor máximo esperado em indicador percentual (aplicado ao IRS3001)", F_NORMAL, alinhamento=ESQUERDA)
    escrever(ws_par, "B3", 100, F_ENTRADA, FMT_2, borda=True, preenchimento=FILL_EDITAVEL)
    escrever(ws_par, "A4", "Limite de massa per capita do IRS1004 (kg/hab.dia)", F_NORMAL, alinhamento=ESQUERDA)
    escrever(ws_par, "B4", 3, F_ENTRADA, FMT_2, borda=True, preenchimento=FILL_EDITAVEL)
    nota(ws_par, "A6", "Os dois critérios são os mesmos usados no ETL (scripts/etl_sqlite.py). O limite de 3 kg/hab.dia é uma escolha do grupo.")
    nota(ws_par, "A7", "Alterar aqui muda apenas esta planilha; o banco de dados não é modificado.")
    larguras(ws_par, {"A": 70, "B": 14})

    # ------------------------------------------------------------ Descritiva
    titulo(ws_desc, "Estatística descritiva dos indicadores",
           "Municípios respondentes. Média ponderada: peso = população total do município.")
    cabecalho(ws_desc, 4, ["Código", "Indicador", "Unidade", "N", "Média", "Mediana", "Desvio-padrão",
                           "Mínimo", "1º quartil", "3º quartil", "Máximo", "% de municípios = 0",
                           "% de municípios = 100", "Média ponderada por população", "Ponderada − simples"])
    for i, codigo in enumerate(an.INDICADORES):
        r = 5 + i
        v = rng(codigo)
        escrever(ws_desc, f"A{r}", codigo, F_NEGRITO, borda=True)
        escrever(ws_desc, f"B{r}", nomes[codigo], F_NORMAL, alinhamento=ESQUERDA, borda=True)
        escrever(ws_desc, f"C{r}", unidades[codigo], F_NORMAL, borda=True)
        formulas = {
            "D": (f"=COUNT({v})", FMT_INT),
            "E": (f"=AVERAGE({v})", FMT_2),
            "F": (f"=MEDIAN({v})", FMT_2),
            "G": (f"=STDEV({v})", FMT_2),
            "H": (f"=MIN({v})", FMT_2),
            "I": (f"=QUARTILE({v},1)", FMT_2),
            "J": (f"=QUARTILE({v},3)", FMT_2),
            "K": (f"=MAX({v})", FMT_2),
            "L": (f"=COUNTIF({v},0)/D{r}", FMT_PCT),
            "M": (f"=COUNTIF({v},100)/D{r}", FMT_PCT),
            "N": (f"=SUMPRODUCT({v},{pop})/SUM({pop})", FMT_2),
            "O": (f"=N{r}-E{r}", FMT_2),
        }
        for col, (f, fmt) in formulas.items():
            escrever(ws_desc, f"{col}{r}", f, F_NORMAL, fmt, borda=True)
        ws_desc.row_dimensions[r].height = 42
    nota(ws_desc, "A12", "Leitura: quando a mediana é 0 e a média é alta (caso do IRS3002), a distribuição se concentra nos extremos; "
                         "interprete média, mediana e média ponderada em conjunto.")
    nota(ws_desc, "A13", "Os valores sinalizados na aba Qualidade_Dados estão incluídos nestes cálculos.")
    larguras(ws_desc, {"A": 10, "B": 52, "C": 12, "D": 9, "E": 10, "F": 10, "G": 12, "H": 10, "I": 10,
                       "J": 10, "K": 10, "L": 14, "M": 14, "N": 16, "O": 14})
    ws_desc.freeze_panes = "C5"

    # ------------------------------------------------------------ Ranking_UF
    ranking = an.ranking_uf(df)
    totais = totais_uf.set_index("uf")["municipios_total"].to_dict()
    titulo(ws_rank, "Ranking de UFs - disposição final inadequada (IRS3002)",
           "Posição 1 = pior cenário (maior percentual). UFs empatadas dividem a posição.")
    cabecalho(ws_rank, 4, ["UF", "Municípios no SINISA (total)", "Municípios respondentes", "Taxa de resposta",
                           "IRS3002 média simples (%)", "Posição (média simples)",
                           "IRS3002 média ponderada (%)", "Posição (ponderada)"])
    primeira, ultima_uf = 5, 4 + len(ranking)
    for i, uf in enumerate(ranking["uf"]):
        r = 5 + i
        escrever(ws_rank, f"A{r}", uf, F_NEGRITO, borda=True)
        escrever(ws_rank, f"B{r}", int(totais[uf]), F_ENTRADA, FMT_INT, borda=True)
        escrever(ws_rank, f"C{r}", f"=COUNTIF({ufs},A{r})", F_NORMAL, FMT_INT, borda=True)
        escrever(ws_rank, f"D{r}", f"=C{r}/B{r}", F_NORMAL, FMT_PCT, borda=True)
        escrever(ws_rank, f"E{r}", f"=AVERAGEIF({ufs},A{r},{rng('IRS3002')})", F_NORMAL, FMT_2, borda=True)
        escrever(ws_rank, f"F{r}", f"=RANK(E{r},$E${primeira}:$E${ultima_uf},0)", F_NORMAL, "0", borda=True)
        escrever(ws_rank, f"G{r}",
                 f"=SUMPRODUCT(({ufs}=A{r})*{pop}*{rng('IRS3002')})/SUMIF({ufs},A{r},{pop})",
                 F_NORMAL, FMT_2, borda=True)
        escrever(ws_rank, f"H{r}", f"=RANK(G{r},$G${primeira}:$G${ultima_uf},0)", F_NORMAL, "0", borda=True)
    ws_rank.conditional_formatting.add(
        f"A{primeira}:H{ultima_uf}",
        FormulaRule(formula=[f'$A{primeira}="{an.UF_RECORTE}"'], fill=FILL_DESTAQUE))
    nota(ws_rank, f"A{ultima_uf + 2}", "Coluna B: total de municípios da UF na planilha do SINISA (digitado a partir do banco de dados; texto azul).")
    nota(ws_rank, f"A{ultima_uf + 3}", f"Linha destacada: {an.UF_RECORTE}. A ordem das linhas segue a média simples dos dados atuais; "
                                        "se os dados mudarem, use as colunas de posição.")
    nota(ws_rank, f"A{ultima_uf + 4}", "O DF tem apenas 1 município; interprete sua posição com cautela.")

    grafico = BarChart()
    grafico.type = "col"
    grafico.title = "IRS3002 por UF: média simples x média ponderada (%)"
    grafico.y_axis.title = "% de resíduos em disposição inadequada"
    grafico.x_axis.title = "UF"
    grafico.add_data(Reference(ws_rank, min_col=5, min_row=4, max_row=ultima_uf), titles_from_data=True)
    grafico.add_data(Reference(ws_rank, min_col=7, min_row=4, max_row=ultima_uf), titles_from_data=True)
    grafico.set_categories(Reference(ws_rank, min_col=1, min_row=5, max_row=ultima_uf))
    grafico.x_axis.delete = False
    grafico.y_axis.delete = False
    grafico.height, grafico.width = 10, 26
    ws_rank.add_chart(grafico, "J4")
    larguras(ws_rank, {"A": 8, "B": 16, "C": 16, "D": 12, "E": 16, "F": 14, "G": 16, "H": 14})
    ws_rank.freeze_panes = "B5"

    # --------------------------------------------------------------- Regioes
    regioes = an.resumo_regioes(df)
    titulo(ws_reg, "Disposição final inadequada (IRS3002) por região",
           "Probabilidades empíricas: proporção de municípios com IRS3002 igual a 100% ou a 0%.")
    cabecalho(ws_reg, 4, ["Região", "Municípios respondentes", "IRS3002 média simples (%)",
                          "IRS3002 média ponderada (%)", "P(IRS3002 = 100%)", "P(IRS3002 = 0%)"])
    for i, regiao in enumerate(regioes["regiao"]):
        r = 5 + i
        reg = rng("reg")
        escrever(ws_reg, f"A{r}", regiao, F_NEGRITO, borda=True)
        escrever(ws_reg, f"B{r}", f"=COUNTIF({reg},A{r})", F_NORMAL, FMT_INT, borda=True)
        escrever(ws_reg, f"C{r}", f"=AVERAGEIF({reg},A{r},{rng('IRS3002')})", F_NORMAL, FMT_2, borda=True)
        escrever(ws_reg, f"D{r}", f"=SUMPRODUCT(({reg}=A{r})*{pop}*{rng('IRS3002')})/SUMIF({reg},A{r},{pop})",
                 F_NORMAL, FMT_2, borda=True)
        escrever(ws_reg, f"E{r}", f"=COUNTIFS({reg},A{r},{rng('IRS3002')},100)/B{r}", F_NORMAL, FMT_PCT, borda=True)
        escrever(ws_reg, f"F{r}", f"=COUNTIFS({reg},A{r},{rng('IRS3002')},0)/B{r}", F_NORMAL, FMT_PCT, borda=True)
    larguras(ws_reg, {"A": 16, "B": 16, "C": 18, "D": 18, "E": 16, "F": 16})

    # ------------------------------------------------------------- Painel_UF
    titulo(ws_painel, "Painel por UF",
           "Escolha a UF na célula amarela. Compare a UF com o Brasil (municípios respondentes).")
    escrever(ws_painel, "A3", "UF selecionada", F_NEGRITO)
    escrever(ws_painel, "B3", an.UF_RECORTE, F_ENTRADA, borda=True, preenchimento=FILL_EDITAVEL,
             alinhamento=Alignment(horizontal="center"))
    validacao = DataValidation(type="list", formula1=f"=Ranking_UF!$A${primeira}:$A${ultima_uf}", allow_blank=False)
    validacao.error, validacao.errorTitle = "Escolha uma UF da lista.", "UF inválida"
    ws_painel.add_data_validation(validacao)
    validacao.add("B3")
    escrever(ws_painel, "A4", "Municípios respondentes na UF", F_NORMAL)
    escrever(ws_painel, "B4", f"=COUNTIF({ufs},$B$3)", F_NORMAL, FMT_INT, borda=True)
    escrever(ws_painel, "A5", "Taxa de resposta da UF", F_NORMAL)
    escrever(ws_painel, "B5", f"=INDEX(Ranking_UF!$D${primeira}:$D${ultima_uf},MATCH($B$3,Ranking_UF!$A${primeira}:$A${ultima_uf},0))",
             F_NORMAL, FMT_PCT, borda=True)
    escrever(ws_painel, "A6", "Posição no ranking do IRS3002 (média simples; 1 = pior)", F_NORMAL)
    escrever(ws_painel, "B6", f"=INDEX(Ranking_UF!$F${primeira}:$F${ultima_uf},MATCH($B$3,Ranking_UF!$A${primeira}:$A${ultima_uf},0))",
             F_NORMAL, "0", borda=True)
    escrever(ws_painel, "A7", "Posição no ranking do IRS3002 (ponderada; 1 = pior)", F_NORMAL)
    escrever(ws_painel, "B7", f"=INDEX(Ranking_UF!$H${primeira}:$H${ultima_uf},MATCH($B$3,Ranking_UF!$A${primeira}:$A${ultima_uf},0))",
             F_NORMAL, "0", borda=True)
    cabecalho(ws_painel, 9, ["Indicador", "UF: média simples", "UF: mediana", "UF: média ponderada",
                             "Brasil: média simples", "Brasil: média ponderada", "UF − Brasil (ponderadas)"])
    for i, codigo in enumerate(an.INDICADORES):
        r = 10 + i
        v = rng(codigo)
        escrever(ws_painel, f"A{r}", f"{codigo} - {nomes[codigo]}", F_NORMAL, alinhamento=ESQUERDA, borda=True)
        escrever(ws_painel, f"B{r}", f"=AVERAGEIF({ufs},$B$3,{v})", F_NORMAL, FMT_2, borda=True)
        ws_painel[f"C{r}"] = ArrayFormula(f"C{r}", f"=MEDIAN(IF({ufs}=$B$3,{v}))")
        ws_painel[f"C{r}"].font, ws_painel[f"C{r}"].number_format, ws_painel[f"C{r}"].border = F_NORMAL, FMT_2, BORDA
        ws_painel[f"C{r}"].alignment = Alignment(vertical="center")
        escrever(ws_painel, f"D{r}", f"=SUMPRODUCT(({ufs}=$B$3)*{pop}*{v})/SUMIF({ufs},$B$3,{pop})", F_NORMAL, FMT_2, borda=True)
        escrever(ws_painel, f"E{r}", f"=Descritiva!E{5 + i}", F_NORMAL, FMT_2, borda=True)
        escrever(ws_painel, f"F{r}", f"=Descritiva!N{5 + i}", F_NORMAL, FMT_2, borda=True)
        escrever(ws_painel, f"G{r}", f"=D{r}-F{r}", F_NORMAL, FMT_2, borda=True)
        ws_painel.row_dimensions[r].height = 30
    nota(ws_painel, "A17", "Para IRS3002, valores menores são melhores (menos resíduo em lixão ou aterro controlado).")
    nota(ws_painel, "A18", "Contexto: este painel apresenta dados de resíduos urbanos municipais e não mede a gestão de resíduos de empresas.")
    larguras(ws_painel, {"A": 66, "B": 16, "C": 14, "D": 18, "E": 16, "F": 18, "G": 18})

    # ------------------------------------------------------------ Associacoes
    titulo(ws_assoc, "Associações entre indicadores",
           "Correlação, regressão linear simples e probabilidades condicionais (fórmulas ligadas à aba Dados).")
    escrever(ws_assoc, "A4", "1. Correlação de Pearson", F_NEGRITO)
    cabecalho(ws_assoc, 5, [""] + an.INDICADORES)
    for i, linha in enumerate(an.INDICADORES):
        r = 6 + i
        escrever(ws_assoc, f"A{r}", linha, F_NEGRITO, borda=True)
        for j, coluna in enumerate(an.INDICADORES):
            letra = chr(ord("B") + j)
            escrever(ws_assoc, f"{letra}{r}", f"=CORREL({rng(linha)},{rng(coluna)})", F_NORMAL, FMT_2, borda=True,
                     alinhamento=Alignment(horizontal="center"))
    ws_assoc.conditional_formatting.add(
        "B6:G11", ColorScaleRule(start_type="num", start_value=-1, start_color="F8696B",
                                 mid_type="num", mid_value=0, mid_color="FFFFFF",
                                 end_type="num", end_value=1, end_color="63BE7B"))
    nota(ws_assoc, "A12", "Pearson mede associação linear; como muitos indicadores se concentram em 0, veja também Spearman na aba Testes_Python.")

    escrever(ws_assoc, "A14", "2. Regressão linear simples (y = intercepto + inclinação x)", F_NEGRITO)
    cabecalho(ws_assoc, 15, ["Modelo (y ~ x)", "N", "Intercepto", "Inclinação", "R²", "Interpretação"])
    modelos = [("IRS3010", "IRS0005", "Cada ponto percentual a mais de cobertura da coleta seletiva se associa a esta variação, em pontos percentuais, na recuperação de resíduos."),
               ("IRS3001", "IRS0005", "Cada ponto percentual a mais de cobertura da coleta seletiva se associa a esta variação, em pontos percentuais, no desempenho da coleta seletiva.")]
    for i, (y, x, interpretacao) in enumerate(modelos):
        r = 16 + i
        escrever(ws_assoc, f"A{r}", f"{y} ~ {x}", F_NEGRITO, borda=True)
        escrever(ws_assoc, f"B{r}", f"=COUNT({rng(y)})", F_NORMAL, FMT_INT, borda=True)
        escrever(ws_assoc, f"C{r}", f"=INTERCEPT({rng(y)},{rng(x)})", F_NORMAL, "0.000", borda=True)
        escrever(ws_assoc, f"D{r}", f"=SLOPE({rng(y)},{rng(x)})", F_NORMAL, "0.0000", borda=True)
        escrever(ws_assoc, f"E{r}", f"=RSQ({rng(y)},{rng(x)})", F_NORMAL, "0.000", borda=True)
        escrever(ws_assoc, f"F{r}", interpretacao, F_NORMAL, alinhamento=ESQUERDA, borda=True)
        ws_assoc.row_dimensions[r].height = 42
    nota(ws_assoc, "A18", "R² baixo indica que o ajuste linear explica pouco da variação; a relação é forte em ordem (Spearman) mas não é linear.")

    escrever(ws_assoc, "A20", "3. Probabilidades empíricas condicionais", F_NEGRITO)
    cabecalho(ws_assoc, 21, ["Evento", "Municípios no grupo", "Probabilidade"])
    g, k = rng("IRS0005"), rng("IRS3010")
    prob = [
        ("P(IRS3010 = 0): município sem recuperação", f"=COUNT({k})", f"=COUNTIF({k},0)/B22"),
        ("P(IRS3010 = 0 | IRS0005 = 0): sem recuperação, dado que não há cobertura de coleta seletiva",
         f"=COUNTIF({g},0)", f"=COUNTIFS({g},0,{k},0)/B23"),
        ("P(IRS3010 = 0 | IRS0005 > 0): sem recuperação, dado que há cobertura de coleta seletiva",
         f'=COUNTIF({g},">0")', f'=COUNTIFS({g},">0",{k},0)/B24'),
    ]
    for i, (evento, grupo, formula) in enumerate(prob):
        r = 22 + i
        escrever(ws_assoc, f"A{r}", evento, F_NORMAL, alinhamento=ESQUERDA, borda=True)
        escrever(ws_assoc, f"B{r}", grupo, F_NORMAL, FMT_INT, borda=True)
        escrever(ws_assoc, f"C{r}", formula, F_NORMAL, FMT_PCT, borda=True)
        ws_assoc.row_dimensions[r].height = 30
    nota(ws_assoc, "A26", "Associação não implica causalidade: os indicadores são medidos nos mesmos municípios e podem refletir a estrutura de serviços como um todo.")
    larguras(ws_assoc, {"A": 62, "B": 14, "C": 14, "D": 14, "E": 12, "F": 70, "G": 12})

    # ----------------------------------------------------------- Testes_Python
    titulo(ws_py, "Testes calculados em Python (valores fixos)",
           "Gerados por scripts/analise_estatistica.py com scipy. Não recalculam se os dados mudarem.")
    escrever(ws_py, "A4", "1. Correlação de Spearman (ordem dos valores)", F_NEGRITO)
    cabecalho(ws_py, 5, [""] + an.INDICADORES)
    spearman = an.matriz_correlacao(df, "spearman")
    for i, linha in enumerate(an.INDICADORES):
        r = 6 + i
        escrever(ws_py, f"A{r}", linha, F_NEGRITO, borda=True)
        for j, coluna in enumerate(an.INDICADORES):
            escrever(ws_py, f"{chr(ord('B') + j)}{r}", float(spearman.loc[linha, coluna]), F_ENTRADA, FMT_2, borda=True,
                     alinhamento=Alignment(horizontal="center"))
    ws_py.conditional_formatting.add(
        "B6:G11", ColorScaleRule(start_type="num", start_value=-1, start_color="F8696B",
                                 mid_type="num", mid_value=0, mid_color="FFFFFF",
                                 end_type="num", end_value=1, end_color="63BE7B"))

    t = an.comparar_uf_com_demais(df)
    escrever(ws_py, "A13", f"2. Teste de Mann-Whitney: {t['uf']} x demais UFs ({t['indicador']})", F_NEGRITO)
    cabecalho(ws_py, 14, ["Medida", "Valor"])
    linhas = [
        (f"Municípios de {t['uf']}", t["n_uf"], FMT_INT),
        ("Municípios das demais UFs", t["n_demais"], FMT_INT),
        (f"Média em {t['uf']} (%)", t["media_uf"], FMT_2),
        ("Média nas demais UFs (%)", t["media_demais"], FMT_2),
        (f"Mediana em {t['uf']} (%)", t["mediana_uf"], FMT_2),
        ("Mediana nas demais UFs (%)", t["mediana_demais"], FMT_2),
        ("Estatística U", t["u"], "#,##0.0"),
        ("p-valor (bilateral)", t["p_valor"], "0.00E+00"),
        (f"Probabilidade de um município de {t['uf']} ter valor menor que o de um município das demais UFs (empates contam metade)",
         t["prob_uf_menor"], FMT_PCT),
    ]
    for i, (medida, valor, fmt) in enumerate(linhas):
        r = 15 + i
        escrever(ws_py, f"A{r}", medida, F_NORMAL, alinhamento=ESQUERDA, borda=True)
        escrever(ws_py, f"B{r}", float(valor), F_ENTRADA, fmt, borda=True)
    ws_py.row_dimensions[23].height = 42
    nota(ws_py, "A25", "O teste de Mann-Whitney não supõe distribuição normal. Como as medianas coincidem em 0, a diferença vem da proporção de municípios com valores altos.")
    larguras(ws_py, {"A": 70, "B": 14, "C": 12, "D": 12, "E": 12, "F": 12, "G": 12})

    # ---------------------------------------------------------- Qualidade_Dados
    titulo(ws_qual, "Qualidade dos dados", "Valores sinalizados pelos critérios da aba Parametros (mantidos nos cálculos).")
    cabecalho(ws_qual, 4, ["Indicador", "Critério de sinalização", "Valores sinalizados", "Maior valor",
                           "Média com todos os valores", "Média sem os sinalizados", "Diferença"])
    regras = [("IRS3001", "valor > limite percentual (Parametros!B3)", "sinal_3001"),
              ("IRS1004", "valor > limite de massa per capita (Parametros!B4)", "sinal_1004")]
    for i, (codigo, regra, sinal) in enumerate(regras):
        r = 5 + i
        escrever(ws_qual, f"A{r}", codigo, F_NEGRITO, borda=True)
        escrever(ws_qual, f"B{r}", regra, F_NORMAL, alinhamento=ESQUERDA, borda=True)
        escrever(ws_qual, f"C{r}", f"=SUM({rng(sinal)})", F_NORMAL, FMT_INT, borda=True)
        escrever(ws_qual, f"D{r}", f"=MAX({rng(codigo)})", F_NORMAL, FMT_2, borda=True)
        escrever(ws_qual, f"E{r}", f"=AVERAGE({rng(codigo)})", F_NORMAL, "0.000", borda=True)
        escrever(ws_qual, f"F{r}", f"=AVERAGEIF({rng(sinal)},0,{rng(codigo)})", F_NORMAL, "0.000", borda=True)
        escrever(ws_qual, f"G{r}", f"=F{r}-E{r}", F_NORMAL, "0.000", borda=True)
        ws_qual.row_dimensions[r].height = 30
    nota(ws_qual, "A8", "Para localizar os municípios sinalizados, filtre a coluna L ou M da aba Dados pelo valor 1.")
    nota(ws_qual, "A9", "O IRS3001 é a razão entre a massa da coleta seletiva e a massa da coleta domiciliar; valores acima de 100% indicam inconsistência de preenchimento.")
    larguras(ws_qual, {"A": 12, "B": 52, "C": 18, "D": 14, "E": 18, "F": 18, "G": 12})

    # ---------------------------------------------------------------- Leia-me
    titulo(ws_leia, "Planilha de análise estatística - gestão de resíduos sólidos urbanos",
           "Projeto de Extensão do 4º semestre - FATEC São Bernardo do Campo")
    escrever(ws_leia, "A4", "Fonte dos dados", F_NEGRITO)
    escrever(ws_leia, "A5", "Ministério das Cidades - SINISA 2025 (ano de referência 2024): planilha de indicadores de resíduos sólidos "
                            "e Glossário de Indicadores SINISA 2025.", F_NORMAL, alinhamento=ESQUERDA)
    escrever(ws_leia, "A6", "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento/sinisa/resultados-sinisa/"
                            "Glossario_Indicadores_SINISA_2025.pdf", F_NOTA)
    escrever(ws_leia, "A8", "Resumo da base", F_NEGRITO)
    resumo = [
        ("Municípios na planilha do SINISA", f"=SUM(Ranking_UF!B{primeira}:B{ultima_uf})", FMT_INT),
        ("Municípios respondentes (entram na análise)", f"=COUNTA({rng('cod')})", FMT_INT),
        ("Taxa de resposta nacional", "=B10/B9", FMT_PCT),
        ("Indicadores analisados", f"=COUNTA(Descritiva!A5:A{4 + len(an.INDICADORES)})", "0"),
    ]
    for i, (rotulo, formula, fmt) in enumerate(resumo):
        r = 9 + i
        escrever(ws_leia, f"A{r}", rotulo, F_NORMAL, borda=True)
        escrever(ws_leia, f"B{r}", formula, F_NORMAL, fmt, borda=True)
    escrever(ws_leia, "A14", "Abas", F_NEGRITO)
    abas = [
        ("Parametros", "Critérios de sinalização de valores suspeitos (células editáveis)."),
        ("Descritiva", "Média, mediana, desvio-padrão, quartis, % em 0 e em 100 e média ponderada por população."),
        ("Ranking_UF", "Ranking das UFs no IRS3002 (média simples e ponderada), taxa de resposta e gráfico."),
        ("Regioes", "IRS3002 por região, com probabilidades empíricas."),
        ("Painel_UF", "Escolha uma UF e compare com o Brasil."),
        ("Associacoes", "Correlação de Pearson, regressão linear simples e probabilidades condicionais."),
        ("Testes_Python", "Spearman e teste de Mann-Whitney (valores fixos calculados em Python)."),
        ("Qualidade_Dados", "Valores sinalizados e efeito sobre as médias."),
        ("Dados", "Base de municípios respondentes (um por linha), com filtros."),
    ]
    for i, (aba, descricao) in enumerate(abas):
        r = 15 + i
        escrever(ws_leia, f"A{r}", aba, F_NEGRITO, borda=True)
        escrever(ws_leia, f"B{r}", descricao, F_NORMAL, alinhamento=ESQUERDA, borda=True)
    base = 15 + len(abas) + 1
    escrever(ws_leia, f"A{base}", "Convenções", F_NEGRITO)
    escrever(ws_leia, f"A{base + 1}", "Texto azul", F_ENTRADA)
    escrever(ws_leia, f"B{base + 1}", "Valor digitado ou importado do banco de dados.", F_NORMAL)
    escrever(ws_leia, f"A{base + 2}", "Texto preto", F_NORMAL)
    escrever(ws_leia, f"B{base + 2}", "Fórmula do Excel.", F_NORMAL)
    escrever(ws_leia, f"A{base + 3}", "Fundo amarelo", F_NORMAL, preenchimento=FILL_EDITAVEL)
    escrever(ws_leia, f"B{base + 3}", "Célula que o usuário pode alterar.", F_NORMAL)
    escrever(ws_leia, f"A{base + 5}", "Premissas e limitações", F_NEGRITO)
    limites = [
        "Só entram municípios que responderam ao módulo de resíduos; os que não responderam ficam fora (taxa de resposta por UF na aba Ranking_UF).",
        "Média simples dá o mesmo peso a cada município; a média ponderada usa a população total do município como peso.",
        "O IRS3002 se concentra em 0 e em 100: interprete média, mediana e média ponderada em conjunto.",
        "Os valores sinalizados na aba Qualidade_Dados foram mantidos nos cálculos.",
        "Correlação, regressão e probabilidade condicional indicam associação, não causalidade.",
        "O IRS3002 mede resíduos sólidos urbanos municipais; não mede resíduos industriais nem a gestão ambiental de empresas.",
        "Posições empatadas no ranking recebem o mesmo número.",
    ]
    for i, texto in enumerate(limites):
        escrever(ws_leia, f"A{base + 6 + i}", f"{i + 1}. {texto}", F_NORMAL, alinhamento=Alignment(wrap_text=False))
    larguras(ws_leia, {"A": 46, "B": 90})

    return wb


def executar():
    conn = sqlite3.connect(an.CAMINHO_BANCO)
    try:
        df = an.carregar_dados(conn)
        catalogo = an.carregar_catalogo(conn)
        totais_uf = an.carregar_totais_por_uf(conn)
    finally:
        conn.close()

    wb = montar(df, catalogo, totais_uf)
    os.makedirs(os.path.dirname(CAMINHO_SAIDA), exist_ok=True)
    wb.save(CAMINHO_SAIDA)
    print(f"Planilha gerada: {CAMINHO_SAIDA}")
    print(f"Municípios na aba Dados: {len(df)}")


if __name__ == "__main__":
    executar()