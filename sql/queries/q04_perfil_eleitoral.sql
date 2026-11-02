/* ---------------------------------------------------------------------------
   QUERY : q04_perfil_eleitoral_municipio.sql
   OBJETIVO : perfil do eleitorado por municipio (ex.: faixa etaria 2024)
   LOGICA : fact_eleitorado_perfil guarda contagens por (perfil x secao);
            somar por indicador desejado, filtrando por ano + municipio.
   NOTA  : secao pode nao existir em dim_secao para anos sem local_votacao,
           mas a aglutinacao e direta pela fact.
--------------------------------------------------------------------------- */
SELECT p.cd_municipio_tse,
       m.nm_municipio_tse,
       p.ds_faixa_etaria,
       SUM(p.qt_eleitores_perfil) AS eleitores,
       ROUND(100.0 * SUM(p.qt_eleitores_perfil) /
             NULLIF(SUM(SUM(p.qt_eleitores_perfil)) OVER (PARTITION BY p.cd_municipio_tse), 0), 2) AS pct
FROM fact_eleitorado_perfil p
LEFT JOIN dim_municipio m ON m.cd_municipio_tse = p.cd_municipio_tse
WHERE p.ano_eletivo = 2024
  AND p.cd_municipio_tse = '71072'          -- exemplo: um municipio especifico
GROUP BY 1,2,3
ORDER BY eleitores DESC;