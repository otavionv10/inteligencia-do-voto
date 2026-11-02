/* ---------------------------------------------------------------------------
   QUERY : q01_eleitores_por_municipio.sql
   OBJETIVO : eleitores aptos por municipio e ano (via fact_eleitorado_local)
   JOIN : dim_municipio (mapa TSE <-> IBGE)
   NOTA : aptos por secao so existem para 2022/2024/2026.
--------------------------------------------------------------------------- */
SELECT l.ano_eletivo,
       m.cd_municipio_ibge,
       l.cd_municipio_tse,
       m.nm_municipio_tse,
       SUM(l.qt_eleitor_secao) AS aptos
FROM fact_eleitorado_local l
LEFT JOIN dim_municipio m
       ON m.cd_municipio_tse = l.cd_municipio_tse
WHERE l.nr_turno = 1
GROUP BY 1,2,3,4
ORDER BY 1, SUM(l.qt_eleitor_secao) DESC;