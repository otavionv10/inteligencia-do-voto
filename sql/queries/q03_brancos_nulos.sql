/* ---------------------------------------------------------------------------
   QUERY : q03_brancos_nulos_por_municipio.sql
   OBJETIVO : % de votos brancos/nulos por municipio (ex.: Governador 1T 2022)
   LOGICA : na fact_votacao_secao, votos sem candidato tem NR_VOTAVEL especial:
            95 = BRANCOS, 96 = NULOS (fonte: TSE, regras em _sql/LOGICA.md)
--------------------------------------------------------------------------- */
SELECT cd_municipio_tse,
       SUM(CASE WHEN nr_votavel = 95 THEN qt_votos ELSE 0 END) AS brancos,
       SUM(CASE WHEN nr_votavel = 96 THEN qt_votos ELSE 0 END) AS nulos,
       SUM(qt_votos)                                           AS total,
       ROUND(100.0 * (SUM(CASE WHEN nr_votavel IN (95,96) THEN qt_votos ELSE 0 END)) / SUM(qt_votos), 2) AS pct_brancos_nulos
FROM fact_votacao_secao
WHERE ano_eletivo = 2022 AND nr_turno = 1
  AND UPPER(ds_cargo) = 'GOVERNADOR'
GROUP BY 1
HAVING SUM(qt_votos) > 0
ORDER BY pct_brancos_nulos DESC
LIMIT 30;