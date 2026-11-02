/* ---------------------------------------------------------------------------
   CAMADA ANALITICA 03 - ANALISES PRONTAS (exemplos)
   1) Candidatos mais votados (ranking estadual por cargo/ano)
   2) Cidades que elegeram cada candidato (mais votado em cada municipio)
   3) Cidades que mais votaram em ESQUERDA ou DIREITA (share sobre validos)
   4) Zona eleitoral que mais votou em partido/candidato
--------------------------------------------------------------------------- */

/* 1) RANKING ESTADUAL DE CANDIDATOS ---------------------------------------- */
CREATE OR REPLACE VIEW vw_ranking_candidatos AS
SELECT ano_eletivo, nr_turno, cargo,
       nm_candidato, sg_partido, campo,
       SUM(votos) AS votos,
       RANK() OVER (PARTITION BY ano_eletivo, nr_turno, cargo
                    ORDER BY SUM(votos) DESC) AS posicao
  FROM agg_voto_municipio_candidato
 GROUP BY ano_eletivo, nr_turno, cargo, nm_candidato, sg_partido, campo;

/* 2) CIDADES QUE ELEGERAM CADA CANDIDATO ----------------------------------- */
CREATE OR REPLACE VIEW vw_cidades_vencedor AS
WITH r AS (
    SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
           nr_candidato, nm_candidato, sg_partido, campo, votos,
           RANK() OVER (PARTITION BY ano_eletivo, nr_turno, cargo, cd_municipio_tse
                        ORDER BY votos DESC) AS rk
      FROM agg_voto_municipio_candidato
)
SELECT r.ano_eletivo, r.nr_turno, r.cargo, r.cd_municipio_tse, m.nm_municipio_tse,
       r.nr_candidato, r.nm_candidato, r.sg_partido, r.campo, r.votos
  FROM r
  JOIN dim_municipio m USING (cd_municipio_tse)
 WHERE r.rk = 1;

/* 3) CIDADES MAIS ESQUERDA / DIREITA (share do campo sobre votos validos) -- */
CREATE OR REPLACE VIEW vw_cidade_por_campo AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, campo,
       SUM(votos) AS votos_campo,
       MAX(validos) AS validos,
       ROUND(100.0 * SUM(votos) / MAX(NULLIF(validos, 0)), 2) AS share_validos_pct
  FROM agg_voto_municipio_partido
 WHERE campo IS NOT NULL
 GROUP BY ano_eletivo, nr_turno, cargo, cd_municipio_tse, campo;

/* 4) ZONA ELEITORAL QUE MAIS VOTOU EM CANDIDATO/PARTIDO -------------------- */
CREATE OR REPLACE VIEW vw_ranking_zona_candidato AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
       nm_candidato, sg_partido, campo,
       SUM(votos) AS votos,
       MAX(validos) AS validos,
       ROUND(100.0 * SUM(votos) / MAX(NULLIF(validos, 0)), 2) AS share_validos_pct,
       RANK() OVER (PARTITION BY ano_eletivo, nr_turno, cargo
                    ORDER BY SUM(votos) DESC) AS posicao
  FROM agg_voto_zona_candidato
 GROUP BY ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
          nm_candidato, sg_partido, campo;