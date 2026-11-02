/* ---------------------------------------------------------------------------
   QUERY : q10_abstencao_x_indicadores.sql
   OBJETIVO : abstencao municipal x indicadores IBGE (IDHM renda, densidade,
              PIB per capita). Correlacao de Pearson + faixas de IDH-renda.
   BASE : vw_abstencao_secao (criada pela q08) + dim_municipio enriquecido.
--------------------------------------------------------------------------- */

-- 1) Correlacao (2022, governador 1T)
WITH mun AS (
    SELECT a.cd_municipio_tse,
           SUM(a.aptos)          AS aptos,
           SUM(a.comparecimento) AS cmp,
           100.0 * (1 - SUM(a.comparecimento) / SUM(a.aptos)) AS ab_pct,
           MAX(m.ibge_idhm_renda_2010) AS idh_renda,
           MAX(m.ibge_dens_2022)       AS dens,
           MAX(m.ibge_pib_pc_2023)     AS pib_pc
    FROM vw_abstencao_secao a
    JOIN dim_municipio m USING (cd_municipio_tse)
    WHERE a.ano_eletivo = 2022 AND a.ab_pct BETWEEN 0 AND 70
    GROUP BY 1
)
SELECT ROUND(CORR(ab_pct, idh_renda), 3)         AS r_idh_renda,
       ROUND(CORR(ab_pct, LN(NULLIF(dens, 0))), 3)   AS r_log_densidade,
       ROUND(CORR(ab_pct, LN(NULLIF(pib_pc, 0))), 3) AS r_log_pib_pc,
       COUNT(*) AS n_municipios
FROM mun;

-- 2) Abstencao media por faixa de IDH-renda (2022, governador 1T)
WITH mun AS (
    SELECT a.cd_municipio_tse,
           100.0 * (1 - SUM(a.comparecimento) / SUM(a.aptos)) AS ab_pct,
           MAX(m.ibge_idhm_renda_2010) AS idh_renda
    FROM vw_abstencao_secao a
    JOIN dim_municipio m USING (cd_municipio_tse)
    WHERE a.ano_eletivo = 2022 AND a.ab_pct BETWEEN 0 AND 70
    GROUP BY 1
)
SELECT CASE
         WHEN idh_renda < 0.60 THEN '1. <0,60'
         WHEN idh_renda < 0.70 THEN '2. 0,60-0,70'
         WHEN idh_renda < 0.80 THEN '3. 0,70-0,80'
         ELSE                        '4. >=0,80'
       END AS faixa_idh_renda,
       COUNT(*)             AS n_municipios,
       ROUND(AVG(ab_pct), 2) AS ab_medio,
       ROUND(MIN(ab_pct), 2) AS ab_min,
       ROUND(MAX(ab_pct), 2) AS ab_max
FROM mun
GROUP BY 1
ORDER BY 1;