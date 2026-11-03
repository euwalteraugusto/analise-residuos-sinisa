-- =============================================================================
-- 02_consultas.sql  |  Consultas utilizadas na análise (SQLite 3)
--
-- Projeto de Extensão do 4º semestre - FATEC São Bernardo do Campo
-- Pré-requisito: banco gerado por scripts/etl_sqlite.py (esquema em 01_schema.sql)
--
-- Convenções:
--   * Todos os resultados são de municípios respondentes (4.854 na carga atual).
--   * "Média ponderada" = média dos valores ponderada pela população total do
--     município (municipio.populacao_total).
--   * As consultas usam todos os valores. Para ignorar os valores sinalizados
--     no ETL, acrescente: AND r.flag_qualidade IS NULL
--   * As funções de janela (OVER) e SQRT exigem SQLite 3.35 ou superior.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Q01. Estatística descritiva básica por indicador
-- Objetivo: número de municípios, média, mínimo e máximo de cada indicador.
-- -----------------------------------------------------------------------------
SELECT
    r.codigo_indicador,
    COUNT(r.valor)          AS n_municipios,
    ROUND(AVG(r.valor), 2)  AS media,
    ROUND(MIN(r.valor), 2)  AS minimo,
    ROUND(MAX(r.valor), 2)  AS maximo
FROM resultado_indicador r
GROUP BY r.codigo_indicador
ORDER BY r.codigo_indicador;


-- -----------------------------------------------------------------------------
-- Q02. Mediana por indicador
-- O SQLite não tem função de mediana: ordenamos os valores e pegamos o(s)
-- elemento(s) central(is). Com n par, a mediana é a média dos dois centrais.
-- -----------------------------------------------------------------------------
WITH ordenado AS (
    SELECT
        codigo_indicador,
        valor,
        ROW_NUMBER() OVER (PARTITION BY codigo_indicador ORDER BY valor) AS posicao,
        COUNT(*)     OVER (PARTITION BY codigo_indicador)                AS total
    FROM resultado_indicador
)
SELECT
    codigo_indicador,
    ROUND(AVG(valor), 2) AS mediana
FROM ordenado
WHERE posicao IN ((total + 1) / 2, (total + 2) / 2)
GROUP BY codigo_indicador
ORDER BY codigo_indicador;


-- -----------------------------------------------------------------------------
-- Q03. Desvio-padrão amostral por indicador
-- Raiz da soma dos quadrados dos desvios em relação à média, dividida por (n - 1).
-- -----------------------------------------------------------------------------
WITH com_media AS (
    SELECT
        codigo_indicador,
        valor,
        AVG(valor) OVER (PARTITION BY codigo_indicador) AS media
    FROM resultado_indicador
)
SELECT
    codigo_indicador,
    ROUND(SQRT(SUM((valor - media) * (valor - media)) / (COUNT(*) - 1)), 2) AS desvio_padrao
FROM com_media
GROUP BY codigo_indicador
ORDER BY codigo_indicador;


-- -----------------------------------------------------------------------------
-- Q04. Concentração de valores em 0 e em 100 (forma da distribuição)
-- Objetivo: mostrar que vários indicadores se concentram nos extremos, o que
-- torna a média pouco representativa e a mediana mais informativa.
-- -----------------------------------------------------------------------------
SELECT
    r.codigo_indicador,
    COUNT(*)                                                         AS n_municipios,
    ROUND(100.0 * SUM(CASE WHEN r.valor = 0   THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_igual_a_0,
    ROUND(100.0 * SUM(CASE WHEN r.valor = 100 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_igual_a_100,
    ROUND(100.0 * SUM(CASE WHEN r.valor > 0 AND r.valor < 100 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_intermediario
FROM resultado_indicador r
GROUP BY r.codigo_indicador
ORDER BY r.codigo_indicador;


-- -----------------------------------------------------------------------------
-- Q05. Média simples x média ponderada por população, por indicador
-- Objetivo: comparar o "município típico" (média simples) com a "pessoa típica"
-- (média ponderada pela população).
-- -----------------------------------------------------------------------------
SELECT
    r.codigo_indicador,
    ROUND(AVG(r.valor), 2)                                                   AS media_simples,
    ROUND(SUM(r.valor * m.populacao_total) * 1.0 / SUM(m.populacao_total), 2) AS media_ponderada
FROM resultado_indicador r
JOIN municipio m ON m.cod_ibge = r.cod_ibge
GROUP BY r.codigo_indicador
ORDER BY r.codigo_indicador;


-- -----------------------------------------------------------------------------
-- Q06. Ranking de UFs por disposição final inadequada (IRS3002) - média simples
-- Posição 1 = pior cenário (maior percentual). UFs empatadas dividem a posição.
-- -----------------------------------------------------------------------------
SELECT
    RANK() OVER (ORDER BY AVG(r.valor) DESC) AS posicao_pior,
    m.uf,
    COUNT(*)                                  AS n_municipios,
    ROUND(AVG(r.valor), 2)                    AS media_disposicao_inadequada
FROM resultado_indicador r
JOIN municipio m ON m.cod_ibge = r.cod_ibge
WHERE r.codigo_indicador = 'IRS3002'
GROUP BY m.uf
ORDER BY posicao_pior, m.uf;


-- -----------------------------------------------------------------------------
-- Q07. Ranking de UFs por disposição final inadequada (IRS3002) - ponderado
-- Mesma ideia da Q06, mas cada município pesa conforme sua população.
-- -----------------------------------------------------------------------------
SELECT
    RANK() OVER (ORDER BY SUM(r.valor * m.populacao_total) * 1.0 / SUM(m.populacao_total) DESC) AS posicao_pior,
    m.uf,
    COUNT(*)                                                                                     AS n_municipios,
    ROUND(SUM(r.valor * m.populacao_total) * 1.0 / SUM(m.populacao_total), 2)                    AS media_ponderada
FROM resultado_indicador r
JOIN municipio m ON m.cod_ibge = r.cod_ibge
WHERE r.codigo_indicador = 'IRS3002'
GROUP BY m.uf
ORDER BY posicao_pior, m.uf;


-- -----------------------------------------------------------------------------
-- Q08. Recorte do estado de São Paulo: média simples, mediana e ponderada
-- -----------------------------------------------------------------------------
WITH sp AS (
    SELECT r.codigo_indicador, r.valor, m.populacao_total,
           ROW_NUMBER() OVER (PARTITION BY r.codigo_indicador ORDER BY r.valor) AS posicao,
           COUNT(*)     OVER (PARTITION BY r.codigo_indicador)                  AS total
    FROM resultado_indicador r
    JOIN municipio m ON m.cod_ibge = r.cod_ibge
    WHERE m.uf = 'SP'
)
SELECT
    codigo_indicador,
    COUNT(*)                                                          AS n_municipios,
    ROUND(AVG(valor), 2)                                              AS media_simples,
    ROUND(AVG(CASE WHEN posicao IN ((total + 1) / 2, (total + 2) / 2) THEN valor END), 2) AS mediana,
    ROUND(SUM(valor * populacao_total) * 1.0 / SUM(populacao_total), 2) AS media_ponderada
FROM sp
GROUP BY codigo_indicador
ORDER BY codigo_indicador;


-- -----------------------------------------------------------------------------
-- Q09. Taxa de resposta por UF (cobertura da amostra)
-- Objetivo: mostrar quantos municípios de cada UF entram na análise.
-- -----------------------------------------------------------------------------
SELECT
    uf,
    COUNT(*)                                          AS municipios_total,
    SUM(respondeu)                                    AS respondentes,
    ROUND(100.0 * SUM(respondeu) / COUNT(*), 1)       AS taxa_resposta_pct
FROM municipio
GROUP BY uf
ORDER BY taxa_resposta_pct, uf;


-- -----------------------------------------------------------------------------
-- Q10. Qualidade dos dados: valores sinalizados no ETL, por indicador
-- -----------------------------------------------------------------------------
SELECT
    codigo_indicador,
    flag_qualidade,
    COUNT(*) AS n_valores
FROM resultado_indicador
WHERE flag_qualidade IS NOT NULL
GROUP BY codigo_indicador, flag_qualidade
ORDER BY codigo_indicador;


-- -----------------------------------------------------------------------------
-- Q11. Qualidade dos dados: registros sinalizados, do maior para o menor valor
-- Objetivo: listar os municípios com valores suspeitos para conferência manual.
-- -----------------------------------------------------------------------------
SELECT
    m.uf,
    m.nome_municipio,
    r.codigo_indicador,
    r.valor,
    r.flag_qualidade
FROM resultado_indicador r
JOIN municipio m ON m.cod_ibge = r.cod_ibge
WHERE r.flag_qualidade IS NOT NULL
ORDER BY r.valor DESC
LIMIT 20;
