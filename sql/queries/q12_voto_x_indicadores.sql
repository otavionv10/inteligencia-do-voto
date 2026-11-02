/* ---------------------------------------------------------------------------
   QUERY : q12_voto_x_indicadores.sql
   OBJETIVO : share de votos (2022 Governador 1T) x indicadores IBGE por
              municipio. Correlacoes + share medio por faixa de IDH-renda.
   LOGICA : validos = qt_votos com nr_votavel NOT IN (95 branco, 96 nulo, 97 legenda)
            share_cand = votos do nr_votavel / validos
   NOTA   : Tarcisio = nr_votavel 10 (REPUBLICANOS); Haddad = 13 (PT), SP/2022.
--------------------------------------------------------------------------- */

-- 1) Correlacao share de voto x indicadores
WITH mun AS (
    SELECT v.cd_municipio_tse,
           SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END) AS validos,
           100.0 * SUM(CASE WHEN v.nr_votavel=10 THEN v.qt_votos END)
                 / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END),0) AS sh_rep,
           100.0 * SUM(CASE WHEN v.nr_votavel=13 THEN v.qt_votos END)
                 / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END),0) AS sh_pt,
           MAX(m.ibge_idhm_renda_2010) AS idh_r,
           MAX(m.ibge_dens_2022)       AS dens,
           MAX(m.ibge_pib_pc_2023)     AS pib_pc
    FROM fact_votacao_secao v
    JOIN dim_municipio m USING (cd_municipio_tse)
    WHERE v.ano_eletivo = 2022 AND v.nr_turno = 1 AND UPPER(v.ds_cargo) = 'GOVERNADOR'
    GROUP BY 1
)
SELECT ROUND(CORR(sh_rep, idh_r), 3)     AS r_tar_x_idh,
       ROUND(CORR(sh_pt,  idh_r), 3)     AS r_had_x_idh,
       ROUND(CORR(sh_rep, LN(NULLIF(pib_pc,0))), 3) AS r_tar_x_pib,
       ROUND(CORR(sh_pt,  LN(NULLIF(pib_pc,0))), 3) AS r_had_x_pib,
       ROUND(CORR(sh_rep, LN(NULLIF(dens,1))), 3)   AS r_tar_x_dens,
       ROUND(CORR(sh_pt,  LN(NULLIF(dens,1))), 3)   AS r_had_x_dens,
       COUNT(*) AS n_municipios
FROM mun;

-- 2) Share medio por faixa de IDH-renda
WITH mun AS (
    SELECT v.cd_municipio_tse,
           100.0 * SUM(CASE WHEN v.nr_votavel=10 THEN v.qt_votos END)
                 / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END),0) AS sh_rep,
           100.0 * SUM(CASE WHEN v.nr_votavel=13 THEN v.qt_votos END)
                 / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END),0) AS sh_pt,
           100.0 * SUM(CASE WHEN v.nr_votavel IN (95,96,97) THEN v.qt_votos END)
                 / NULLIF(SUM(v.qt_votos),0) AS sh_wb_null,
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
       ROUND(AVG(sh_tar), 2) AS sh_rep_pct,
       ROUND(AVG(sh_pt), 2)  AS sh_pt_pct,
       ROUND(AVG(sh_bn), 2)  AS sh_brancos_nulos_pct
FROM (SELECT m2.cd_municipio_tse,
             CASE WHEN m2.idh_r < 0.65 THEN '1. <0,65' WHEN m2.idh_r < 0.75 THEN '2. 0,65-0,75'
                  WHEN m2.idh_r < 0.80 THEN '3. 0,75-0,80' ELSE '4. >=0,80' END AS faixa,
             m2.sh_rep AS sh_tar, m2.sh_pt, m2.sh_wb_null AS sh_bn
      FROM mun m2) t
GROUP BY 1
ORDER BY 1;