/* ---------------------------------------------------------------------------
   QUERY : q18_mapa_voto_local_2024.sql
   OBJETIVO : dados para MAPA DE CALOR por local de votacao (2024 Prefeito 1T).
              Idem q17, mas partidos de prefeito mapeados via dim_candidato
              (sg_ue = cd_municipio_tse; candidatos variam por municipio).
   SAIDA  : data/analise/mapa_voto_local_2024.csv
   FIX ADR-008 (2026-09-26): nr_zona entrou no GROUP BY e no JOIN (mesmo fix do q17).
--------------------------------------------------------------------------- */
COPY (
    WITH cand AS (
        SELECT DISTINCT c.nr_candidato, c.sg_ue, c.sg_partido
        FROM dim_candidato c
        WHERE c.ano_eletivo = 2024 AND UPPER(c.ds_cargo) = 'PREFEITO'
    ),
    totals AS (
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               SUM(v.qt_votos) AS votos_totais,
               SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END) AS validos,
               100.0 * SUM(CASE WHEN k.sg_partido = 'PT'   THEN v.qt_votos END)
                     / NULLIF(NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0), 0) AS sh_pt,
               100.0 * SUM(CASE WHEN k.sg_partido = 'PL'   THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_pl,
               100.0 * SUM(CASE WHEN k.sg_partido = 'PSDB' THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_psdb,
               100.0 * SUM(CASE WHEN k.sg_partido = 'MDB'  THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_mdb,
               100.0 * SUM(CASE WHEN k.sg_partido IN ('PSB','PSOL') THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_esq_psb_psol,
               100.0 * SUM(CASE WHEN v.nr_votavel IN (95,96,97) THEN v.qt_votos END)
                     / NULLIF(SUM(v.qt_votos), 0) AS brancos_nulos
        FROM fact_votacao_secao v
        LEFT JOIN cand k
          ON k.sg_ue = v.cd_municipio_tse AND k.nr_candidato = v.nr_votavel
        WHERE v.ano_eletivo = 2024 AND v.nr_turno = 1 AND UPPER(v.ds_cargo) = 'PREFEITO'
        GROUP BY 1, 2, 3
    )
    SELECT t.cd_municipio_tse, m.nm_municipio_tse,
           t.nr_zona, t.nr_local_votacao, l.nm_local_votacao, l.ds_tipo_local,
           l.nr_latitude AS lat, l.nr_longitude AS lon,
           t.votos_totais, t.validos,
           ROUND(t.sh_pt, 2) AS share_pt,
           ROUND(t.sh_pl, 2) AS share_pl,
           ROUND(t.sh_psdb, 2) AS share_psdb,
           ROUND(t.sh_mdb, 2) AS share_mdb,
           ROUND(t.sh_esq_psb_psol, 2) AS share_esq_psb_psol,
           ROUND(t.brancos_nulos, 2) AS brancos_nulos_pct
    FROM totals t
    JOIN dim_municipio m USING (cd_municipio_tse)
    LEFT JOIN dim_local_votacao l
      ON l.ano_eletivo = 2024 AND l.cd_municipio_tse = t.cd_municipio_tse
     AND l.nr_zona = t.nr_zona AND l.nr_local_votacao = t.nr_local_votacao
    ORDER BY t.cd_municipio_tse, t.nr_zona, t.nr_local_votacao
) TO 'D:/Dados_TSE/data/analise/mapa_voto_local_2024.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');