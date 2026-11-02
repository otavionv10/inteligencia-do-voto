/* ---------------------------------------------------------------------------
   QUERY : q07_eleitorado_x_populacao_x_idh.sql
   OBJETIVO : cruza eleitorado (TSE) com indicadores IBGE por municipio
              (proporcao eleitores/populacao, PIB per capita, IDHM)
   FONTE   : dim_municipio enriquecido (enrich_ibge.py - censo 2022, PIB 2023,
             IDHM 2010 Atlas PNUD). Unidades: pib_2023_mil = R$ mil;
             pib_pc_2023 = R$; dens = hab/km2.
--------------------------------------------------------------------------- */
SELECT m.cd_municipio_tse,
       m.nm_municipio_tse,
       m.ibge_pop_2022,
       ROUND(m.ibge_dens_2022)                     AS dens_hab_km2,
       e.aptos,
       ROUND(100.0 * e.aptos / m.ibge_pop_2022, 2) AS pct_eleitores_pop,
       m.ibge_pib_pc_2023,
       m.ibge_idhm_2010,
       m.ibge_idhm_renda_2010
FROM dim_municipio m
LEFT JOIN ( SELECT l.cd_municipio_tse, SUM(l.qt_eleitor_secao) AS aptos
            FROM fact_eleitorado_local l
            WHERE l.ano_eletivo = 2026 AND l.nr_turno = 1
            GROUP BY 1 ) e
  ON e.cd_municipio_tse = m.cd_municipio_tse
WHERE m.sg_uf = 'SP' AND m.ibge_pop_2022 IS NOT NULL
ORDER BY aptos DESC
LIMIT 20;