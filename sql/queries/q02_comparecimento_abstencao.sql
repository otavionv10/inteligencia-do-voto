/* ---------------------------------------------------------------------------
   QUERY : q02_comparecimento_abstencao.sql
   OBJETIVO : comparecimento e abstenção por municipio (ex.: Governador 1T 2022)
   LOGICA :
     - aptos (oficial/secáo)    -> fact_eleitorado_local.qt_eleitor_secao
     - comparecimento por cargo -> soma de QT_VOTOS de UM cargo
       (votos = nominais + legenda + brancos + nulos, um voto por eleitor)
     - abstenção = aptos - comparecimento
   ATENCAO : em 2014-2020 nao ha aptos por secao (usar agregado municipal se precisar).
--------------------------------------------------------------------------- */
WITH totais AS (
    SELECT e.cd_municipio_tse,
           SUM(e.qt_eleitor_secao) AS aptos,
           v.cmp
    FROM fact_eleitorado_local e
    JOIN ( SELECT cd_municipio_tse, SUM(qt_votos) AS cmp
           FROM fact_votacao_secao
           WHERE ano_eletivo = 2022 AND nr_turno = 1
             AND UPPER(ds_cargo) = 'GOVERNADOR'
           GROUP BY 1 ) v
      ON v.cd_municipio_tse = e.cd_municipio_tse
    WHERE e.ano_eletivo = 2022 AND e.nr_turno = 1
    GROUP BY 1, v.cmp
)
SELECT cd_municipio_tse, aptos, cmp AS comparecimento,
       aptos - cmp          AS abstencao,
       ROUND(100.0 * (aptos - cmp) / aptos, 2) AS pct_abstencao
FROM totais
ORDER BY pct_abstencao DESC;