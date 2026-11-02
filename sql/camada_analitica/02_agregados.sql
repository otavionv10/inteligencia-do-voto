/* ---------------------------------------------------------------------------
   CAMADA ANALITICA 02 - AGREGADOS MATERIALIZADOS
   Cover 2012-2024 (SP). Base: fact_votacao_secao.
   LINKAGE CANDIDATO (hibrido):
     - 2016+ : sq_candidato
     - 2012/14: nr_votavel = NR_CANDIDATO, mesmo cargo, e UF ('SP' para cargos
               federais/estaduais) ou sigla UE (=cd_municipio_tse) p/ municipais
   TIPOS DE VOTO (TSE): 95=BRANCO, 96=NULO; legenda usa nr_votavel = nr do
   partido com nm_votavel = nome do partido (nao existe nr 97 nestes arquivos).
   validos = NOMINAL + LEGENDA (exclui apenas 95/96).
--------------------------------------------------------------------------- */

PRAGMA threads = 8;

/* 0a. Mapa de candidatos materializado (1 registro/ano/sq) ----------------- */
CREATE OR REPLACE TABLE dim_candidato_map AS
SELECT ano_eletivo, sq_candidato, nr_candidato, nm_candidato, sg_partido,
       nr_partido, nm_partido, campo, nota, cd_cargo,
       UPPER(ds_cargo) AS ds_cargo, sg_uf, sg_ue, nm_ue
  FROM vw_candidato_campo;

/* 0b. Mapa por (ano, nr, cargo, grupo) p/ anos sem sq_candidato (2012/14):
       grupo = sg_ue p/ cargos municipais, sg_uf p/ estaduais/federais      */
CREATE OR REPLACE TABLE dim_candidato_map_nr AS
SELECT ano_eletivo, nr_candidato, ds_cargo, grupo,
       MIN(nm_candidato) AS nm_candidato, MIN(sg_partido) AS sg_partido,
       MIN(nm_partido)   AS nm_partido,   MIN(campo)      AS campo
  FROM (
    SELECT ano_eletivo, nr_candidato, ds_cargo,
           CASE WHEN ds_cargo IN ('PREFEITO','VICE-PREFEITO','VEREADOR')
                THEN CAST(sg_ue AS VARCHAR) ELSE sg_uf END AS grupo,
           nm_candidato, sg_partido, nm_partido, campo
      FROM dim_candidato_map
  )
 GROUP BY 1, 2, 3, 4;

CREATE INDEX IF NOT EXISTS idx_map_sq ON dim_candidato_map(ano_eletivo, sq_candidato);
CREATE INDEX IF NOT EXISTS idx_map_nr ON dim_candidato_map_nr(ano_eletivo, nr_candidato, ds_cargo, grupo);

/* 0c. Base com voto classificado (nominal/legenda/branco-nulo) - MATERIALIZADA
   Dois LEFT JOINs por igualdade (sem OR) -> hash join, rapido. */
CREATE OR REPLACE TABLE fact_voto_camada AS
SELECT v.ano_eletivo, v.nr_turno, UPPER(v.ds_cargo) AS cargo,
       v.cd_municipio_tse, v.nr_zona, v.nr_secao, v.nr_local_votacao,
       v.nr_votavel, v.nm_votavel, v.qt_votos,
       COALESCE(k1.nm_candidato, k2.nm_candidato,
                CASE WHEN v.nr_votavel IN (95,96) THEN NULL ELSE v.nm_votavel END) AS nm_candidato,
       COALESCE(k1.sg_partido, k2.sg_partido, p2.sg_partido) AS sg_partido,
       COALESCE(k1.nm_partido, k2.nm_partido, p2.nm_partido) AS nm_partido,
       COALESCE(k1.campo,      k2.campo,      p2.campo)      AS campo,
       CASE WHEN k1.nr_candidato IS NOT NULL OR k2.nr_candidato IS NOT NULL THEN 'NOMINAL'
            WHEN v.nr_votavel IN (95,96) THEN 'BRANCO_NULO'
            WHEN p2.nr_partido IS NOT NULL THEN 'LEGENDA'
            ELSE 'DESCARTE' END AS tipo_voto
  FROM fact_votacao_secao v
  LEFT JOIN dim_candidato_map k1
         ON k1.ano_eletivo = v.ano_eletivo AND k1.sq_candidato = v.sq_candidato
  LEFT JOIN dim_candidato_map_nr k2
         ON v.sq_candidato IS NULL
        AND k2.ano_eletivo = v.ano_eletivo
        AND k2.nr_candidato = v.nr_votavel
        AND k2.ds_cargo     = UPPER(v.ds_cargo)
        AND k2.grupo        = CASE WHEN UPPER(v.ds_cargo) IN ('PREFEITO','VICE-PREFEITO','VEREADOR')
                                   THEN v.cd_municipio_tse ELSE 'SP' END
  LEFT JOIN dim_partido p2 ON p2.nr_partido = v.nr_votavel;

/* --- Totais por municipio --- */
CREATE OR REPLACE TABLE agg_municipio_totais AS
WITH s AS (
    SELECT ano_eletivo, cargo, cd_municipio_tse, nr_zona, nr_secao,
           MAX(qt_aptos) aptos, MAX(qt_comparecimento) cmp, MAX(qt_abstencoes) ab
      FROM fact_votacao_secao
     GROUP BY 1, 2, 3, 4, 5
)
SELECT ano_eletivo, cargo, cd_municipio_tse,
       SUM(aptos) aptos, SUM(cmp) comparecimento, SUM(ab) abstencoes
  FROM s
 GROUP BY 1, 2, 3;

/* --- Totais por zona --- */
CREATE OR REPLACE TABLE agg_zona_totais AS
WITH s AS (
    SELECT ano_eletivo, cargo, cd_municipio_tse, nr_zona, nr_secao,
           MAX(qt_aptos) aptos, MAX(qt_comparecimento) cmp, MAX(qt_abstencoes) ab
      FROM fact_votacao_secao
     GROUP BY 1, 2, 3, 4, 5
)
SELECT ano_eletivo, cargo, cd_municipio_tse, nr_zona,
       SUM(aptos) aptos, SUM(cmp) comparecimento, SUM(ab) abstencoes
  FROM s
 GROUP BY 1, 2, 3, 4;

/* --- Votos x PARTIDO, nivel municipio (nominal + legenda) --- */
CREATE OR REPLACE TABLE agg_voto_municipio_partido AS
SELECT b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse,
       b.sg_partido, b.nm_partido, b.campo,
       SUM(b.qt_votos) AS votos,
       t.validos
  FROM fact_voto_camada b
  JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
               SUM(qt_votos) validos
          FROM fact_voto_camada
         WHERE tipo_voto IN ('NOMINAL','LEGENDA')
         GROUP BY 1,2,3,4) t
    ON  t.ano_eletivo = b.ano_eletivo AND t.nr_turno = b.nr_turno
    AND t.cargo = b.cargo AND t.cd_municipio_tse = b.cd_municipio_tse
 WHERE b.tipo_voto IN ('NOMINAL','LEGENDA')
 GROUP BY b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse,
          b.sg_partido, b.nm_partido, b.campo;

/* --- Votos x PARTIDO, nivel zona --- */
CREATE OR REPLACE TABLE agg_voto_zona_partido AS
SELECT b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse, b.nr_zona,
       b.sg_partido, b.nm_partido, b.campo,
       SUM(b.qt_votos) AS votos,
       t.validos
  FROM fact_voto_camada b
  JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
               SUM(qt_votos) validos
          FROM fact_voto_camada
         WHERE tipo_voto IN ('NOMINAL','LEGENDA')
         GROUP BY 1,2,3,4,5) t
    ON  t.ano_eletivo = b.ano_eletivo AND t.nr_turno = b.nr_turno
    AND t.cargo = b.cargo AND t.cd_municipio_tse = b.cd_municipio_tse
    AND t.nr_zona = b.nr_zona
 WHERE b.tipo_voto IN ('NOMINAL','LEGENDA')
 GROUP BY b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse, b.nr_zona,
          b.sg_partido, b.nm_partido, b.campo;

/* --- Votos x CANDIDATO, nivel municipio (somente nominal) --- */
CREATE OR REPLACE TABLE agg_voto_municipio_candidato AS
SELECT b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse,
       b.nr_votavel AS nr_candidato, b.nm_candidato, b.sg_partido, b.nm_partido, b.campo,
       SUM(b.qt_votos) AS votos,
       t.validos
  FROM fact_voto_camada b
  JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
               SUM(qt_votos) validos
          FROM fact_voto_camada
         WHERE tipo_voto IN ('NOMINAL','LEGENDA')
         GROUP BY 1,2,3,4) t
    ON  t.ano_eletivo = b.ano_eletivo AND t.nr_turno = b.nr_turno
    AND t.cargo = b.cargo AND t.cd_municipio_tse = b.cd_municipio_tse
 WHERE b.tipo_voto = 'NOMINAL'
 GROUP BY b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse,
          b.nr_votavel, b.nm_candidato, b.sg_partido, b.nm_partido, b.campo;

/* --- Votos x CANDIDATO, nivel zona --- */
CREATE OR REPLACE TABLE agg_voto_zona_candidato AS
SELECT b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse, b.nr_zona,
       b.nr_votavel AS nr_candidato, b.nm_candidato, b.sg_partido, b.nm_partido, b.campo,
       SUM(b.qt_votos) AS votos,
       t.validos
  FROM fact_voto_camada b
  JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
               SUM(qt_votos) validos
          FROM fact_voto_camada
         WHERE tipo_voto IN ('NOMINAL','LEGENDA')
         GROUP BY 1,2,3,4,5) t
    ON  t.ano_eletivo = b.ano_eletivo AND t.nr_turno = b.nr_turno
    AND t.cargo = b.cargo AND t.cd_municipio_tse = b.cd_municipio_tse
    AND t.nr_zona = b.nr_zona
 WHERE b.tipo_voto = 'NOMINAL'
 GROUP BY b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse, b.nr_zona,
          b.nr_votavel, b.nm_candidato, b.sg_partido, b.nm_partido, b.campo;

/* Votos x PARTIDO por LOCAL de votacao (nivel mapa) */
CREATE OR REPLACE TABLE agg_voto_local_partido AS
SELECT b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse, b.nr_local_votacao,
       b.sg_partido, b.nm_partido, b.campo,
       SUM(b.qt_votos) AS votos,
       t.validos
  FROM fact_voto_camada b
  JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_local_votacao,
               SUM(qt_votos) validos
          FROM fact_voto_camada
         WHERE tipo_voto IN ('NOMINAL','LEGENDA')
         GROUP BY 1,2,3,4,5) t
    ON  t.ano_eletivo = b.ano_eletivo AND t.nr_turno = b.nr_turno
    AND t.cargo = b.cargo AND t.cd_municipio_tse = b.cd_municipio_tse
    AND t.nr_local_votacao = b.nr_local_votacao
 WHERE b.tipo_voto IN ('NOMINAL','LEGENDA')
 GROUP BY b.ano_eletivo, b.nr_turno, b.cargo, b.cd_municipio_tse, b.nr_local_votacao,
          b.sg_partido, b.nm_partido, b.campo;

/* --- Views de leitura (share ja calculado) --- */
CREATE OR REPLACE VIEW vw_voto_municipio_partido AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
       sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_municipio_partido;

CREATE OR REPLACE VIEW vw_voto_zona_partido AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
       sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_zona_partido;

CREATE OR REPLACE VIEW vw_voto_local_partido AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_local_votacao,
       sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_local_partido;

CREATE OR REPLACE VIEW vw_voto_municipio_candidato AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
       nr_candidato, nm_candidato, sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_municipio_candidato;

CREATE OR REPLACE VIEW vw_voto_zona_candidato AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
       nr_candidato, nm_candidato, sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_zona_candidato;