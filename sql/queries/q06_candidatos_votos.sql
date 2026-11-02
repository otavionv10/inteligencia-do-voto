/* ---------------------------------------------------------------------------
   QUERY : q06_candidatos_e_resultado_municipio.sql
   OBJETIVO : junta candidatos (dim_candidato) com votacao (fact_votacao_secao)
              -> votos de um candidato x municipio (ex.: Prefeito 1T 2020)
   LOGICA : dim_candidato traz OUTRO registro por turno/registro (sem PK unica),
            filtrar por ano + cargo para evitar duplicacoes.
--------------------------------------------------------------------------- */
SELECT c.nm_urna_candidato,
       c.nr_candidato,
       c.sg_partido,
       f.cd_municipio_tse,
       SUM(f.qt_votos) AS votos
FROM fact_votacao_secao f
JOIN dim_candidato c
  ON c.ano_eletivo = f.ano_eletivo
 AND CAST(c.nr_candidato AS VARCHAR) = CAST(f.nr_votavel AS VARCHAR)
 AND c.sg_uf = 'SP'
WHERE f.ano_eletivo = 2020
  AND f.nr_turno = 1
  AND UPPER(f.ds_cargo) = 'PREFEITO'
  AND f.cd_municipio_tse = '71072'        -- exemplo
  AND f.nr_votavel NOT IN (95, 96, 97)
GROUP BY 1,2,3,4
ORDER BY votos DESC;