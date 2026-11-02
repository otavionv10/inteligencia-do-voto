/* ---------------------------------------------------------------------------
   QUERY : q08_abstencao_secao.sql
   OBJETIVO : abstencao eleitoral por secao (2022 Governador, 2024 Prefeito)*
             e agregacao por municipio.
   LOGICA :
     - aptos (oficial por secao)   = fact_eleitorado_local.qt_eleitor_secao
     - comparecimento (calculado)  = soma de qt_votos de UM cargo majoritario
                                       (nominais+legenda+brancos+nulos)
     - abstencao % = 100 * (1 - comparecimento / aptos)
   LIMPEZA :
     - secoes agregadas (cd_tipo_secao_agregada=1) entram duplicadas no voto
       -> excluidas (dim_secao)
     - outliers de merge (ab<0 ou >70) removidos
   * para 2024 municipal, cargo majoritario = PREFEITO.
--------------------------------------------------------------------------- */
CREATE OR REPLACE VIEW vw_abstencao_secao AS
WITH loc AS (
    SELECT ano_eletivo, cd_municipio_tse, nr_zona, nr_secao, nr_turno,
           MAX(qt_eleitor_secao) AS aptos
    FROM fact_eleitorado_local
    WHERE ano_eletivo IN (2022, 2024)
    GROUP BY 1,2,3,4,5
),
cmp AS (
    SELECT ano_eletivo, cd_municipio_tse, nr_zona, nr_secao, SUM(qt_votos) AS cmp
    FROM fact_votacao_secao
    WHERE (ano_eletivo=2022 AND nr_turno=1 AND UPPER(ds_cargo)='GOVERNADOR')
       OR (ano_eletivo=2024 AND nr_turno=1 AND UPPER(ds_cargo)='PREFEITO')
    GROUP BY 1,2,3,4
)
SELECT l.ano_eletivo, l.cd_municipio_tse, l.nr_zona, l.nr_secao, l.nr_turno,
       l.aptos, COALESCE(v.cmp, 0) AS comparecimento,
       100.0 * (1 - COALESCE(v.cmp, 0) / NULLIF(l.aptos, 0)) AS ab_pct
FROM loc l
LEFT JOIN cmp v USING (ano_eletivo, cd_municipio_tse, nr_zona, nr_secao)
WHERE l.nr_turno = 1;

/* Resumo por municipio (secoes limpas: nao agregadas, ab em [0,70]) */
WITH limpa AS (
    SELECT a.ano_eletivo, a.cd_municipio_tse, a.nr_zona, a.nr_secao, a.aptos,
           a.comparecimento, a.ab_pct,
           COALESCE(s.cd_tipo_secao_agregada, 0) AS agregada
    FROM vw_abstencao_secao a
    LEFT JOIN dim_secao s
      ON s.ano_eletivo = a.ano_eletivo AND s.cd_municipio_tse = a.cd_municipio_tse
     AND s.nr_zona = a.nr_zona AND s.nr_secao = a.nr_secao
    WHERE a.ab_pct BETWEEN 0 AND 70 AND COALESCE(s.cd_tipo_secao_agregada, 0) <> 1
)
SELECT ano_eletivo, cd_municipio_tse,
       m.nm_municipio_tse,
       COUNT(*)                            AS n_secoes,
       SUM(aptos)                          AS aptos,
       SUM(comparecimento)                 AS comparecimento,
       ROUND(100.0 * (1 - SUM(comparecimento)/SUM(aptos)), 2) AS ab_pct,
       ROUND(AVG(ab_pct), 2)               AS ab_media_sec
FROM limpa
LEFT JOIN dim_municipio m USING (cd_municipio_tse)
GROUP BY 1,2,3
ORDER BY ab_pct DESC;