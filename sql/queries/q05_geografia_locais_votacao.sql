/* ---------------------------------------------------------------------------
   QUERY : q05_geografia_locais_votacao.sql
   OBJETIVO : eleitorado por local de votacao com endereco/lat/lon
              (ex.: bairros de um municipio, ate o nivel secao)
   FIX ADR-008 (2026-09-26): nr_zona entrou no JOIN - sem isso, local com o mesmo
   numero em zonas diferentes do municipio duplicava (fan-out) a soma de eleitores.
--------------------------------------------------------------------------- */
SELECT l.nr_zona,
       l.nr_local_votacao,
       l.nm_local_votacao,
       l.nm_bairro,
       l.ds_endereco,
       l.nr_latitude,
       l.nr_longitude,
       COUNT(*)                       AS n_secoes,
       SUM(f.qt_eleitor_secao)        AS eleitores,
       ROUND(MAX(l.nr_latitude), 6)   AS lat,
       ROUND(MAX(l.nr_longitude), 6)  AS lon
FROM dim_local_votacao l
JOIN fact_eleitorado_local f
  ON f.ano_eletivo        = l.ano_eletivo
 AND f.cd_municipio_tse   = l.cd_municipio_tse
 AND f.nr_zona            = l.nr_zona
 AND f.nr_local_votacao   = l.nr_local_votacao
WHERE l.ano_eletivo = 2024
  AND l.cd_municipio_tse = '71072'    -- exemplo
  AND f.nr_turno = 1
GROUP BY 1,2,3,4,5,6,7
ORDER BY eleitores DESC;