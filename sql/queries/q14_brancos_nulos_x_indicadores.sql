/* ---------------------------------------------------------------------------
   QUERY : q14_brancos_nulos_x_indicadores.sql
   OBJETIVO : brancos+nulos (como % do comparecimento) por municipio x IDH/renda
              e PIB per capita (2022, Governador 1T).
   LOGICA : votos total por secao  = soma de qt_votos (nominal+legenda+branco+nulo)
            -> bn_pct = 100 * (95+96+97) / (todos os votos da secao)
--------------------------------------------------------------------------- */
WITH mun AS (
    SELECT v.cd_municipio_tse,
           100.0 * SUM(CASE WHEN v.nr_votavel IN (95,96,97) THEN v.qt_votos END)
                 / NULLIF(SUM(v.qt_votos), 0) AS bn_pct,
           MAX(m.ibge_idhm_renda_2010) AS idh_r,
           MAX(m.ibge_pib_pc_2023)     AS pib_pc
    FROM fact_votacao_secao v
    JOIN dim_municipio m USING (cd_municipio_tse)
    WHERE v.ano_eletivo = 2022 AND v.nr_turno = 1 AND UPPER(v.ds_cargo) = 'GOVERNADOR'
    GROUP BY 1
)
SELECT ROUND(CORR(bn_pct, idh_r), 3)               AS r_bn_idh,
       ROUND(CORR(bn_pct, LN(NULLIF(pib_pc,0))), 3) AS r_bn_pib,
       COUNT(*) AS n_municipios
FROM mun;

WITH mun AS (
    SELECT v.cd_municipio_tse,
           100.0 * SUM(CASE WHEN v.nr_votavel IN (95,96,97) THEN v.qt_votos END)
                 / NULLIF(SUM(v.qt_votos), 0) AS bn_pct,
           MAX(m.ibge_idhm_renda_2010) AS idh_r
    FROM fact_votacao_secao v
    JOIN dim_municipio m USING (cd_municipio_tse)
    WHERE v.ano_eletivo = 2022 AND v.nr_turno = 1 AND UPPER(v.ds_cargo) = 'GOVERNADOR'
    GROUP BY 1
)
SELECT CASE
         WHEN idh_r < 0.65 THEN '1. <0,65'
         WHEN idh_r < 0.75 THEN '2. 0,65-0,75'
         WHEN idh_r < 0.80 THEN '3. 0,75-0,80'
         ELSE                   '4. >=0,80'
       END AS faixa_idh_renda,
       COUNT(*)              AS n_municipios,
       ROUND(AVG(bn_pct), 2) AS bn_medio_pct,
       ROUND(MIN(bn_pct), 2) AS bn_min,
       ROUND(MAX(bn_pct), 2) AS bn_max
FROM mun
GROUP BY 1
ORDER BY 1;