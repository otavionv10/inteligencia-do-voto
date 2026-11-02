/* ---------------------------------------------------------------------------
   QUERY : q17_mapa_voto_local_2022.sql
   OBJETIVO : dados para MAPA DE CALOR por local de votacao (2022 Governador 1T).
              Aggregados por (municipio, ZONA, local) com lat/lon real (dim_local_votacao)
              -> share por partido e por candidato (Tarcisio 10 / Haddad 13).
   SAIDA  : data/analise/mapa_voto_local_2022.csv
   NOTA   : votos validos = nr_votavel NOT IN (95,96,97); local sem geo fica NULL.
   FIX ADR-008 (2026-09-26): nr_zona entrou no GROUP BY e no JOIN - o numero do local
   se repete entre zonas (1.113 pares (municipio,local) de SP colidiam, somando votos
   de ate 4 zonas juntos antes deste fix).
--------------------------------------------------------------------------- */
COPY (
    WITH cand AS (
        SELECT DISTINCT c.nr_candidato, c.sg_partido
        FROM dim_candidato c
        WHERE c.ano_eletivo = 2022 AND UPPER(c.ds_cargo) = 'GOVERNADOR'
          AND c.sg_uf = 'SP' AND c.ds_situacao_candidatura = 'APTO'
    ),
    totals AS (
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               SUM(v.qt_votos)                                   AS votos_totais,
               SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END) AS validos,
               SUM(CASE WHEN v.nr_votavel IN (95,96,97) THEN v.qt_votos END)     AS brancos_nulos,
               SUM(CASE WHEN v.nr_votavel = 10 THEN v.qt_votos END)              AS v_tar,
               SUM(CASE WHEN v.nr_votavel = 13 THEN v.qt_votos END)              AS v_had,
               100.0 * SUM(CASE WHEN k.sg_partido = 'REPUBLICANOS' THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_repub,
               100.0 * SUM(CASE WHEN k.sg_partido = 'PT'    THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_pt,
               100.0 * SUM(CASE WHEN k.sg_partido = 'PSDB'  THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_psdb,
               100.0 * SUM(CASE WHEN k.sg_partido = 'NOVO'  THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_novo,
               100.0 * SUM(CASE WHEN k.sg_partido = 'PDT'   THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_pdt,
               100.0 * SUM(CASE WHEN k.sg_partido = 'UP'    THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END), 0) AS sh_up
        FROM fact_votacao_secao v
        LEFT JOIN cand k ON k.nr_candidato = v.nr_votavel
        WHERE v.ano_eletivo = 2022 AND v.nr_turno = 1 AND UPPER(v.ds_cargo) = 'GOVERNADOR'
        GROUP BY 1,2,3
    )
    SELECT t.cd_municipio_tse,
           m.nm_municipio_tse,
           t.nr_zona,
           t.nr_local_votacao,
           l.nm_local_votacao,
           l.ds_tipo_local,
           l.nr_latitude  AS lat,
           l.nr_longitude AS lon,
           t.votos_totais,
           t.validos,
           t.brancos_nulos,
           ROUND(100.0 * t.v_tar / t.validos, 2) AS share_tarcisio,
           ROUND(100.0 * t.v_had / t.validos, 2) AS share_haddad,
           ROUND(t.sh_repub, 2) AS share_republicanos,
           ROUND(t.sh_pt, 2)    AS share_pt,
           ROUND(t.sh_psdb, 2)  AS share_psdb,
           ROUND(t.sh_novo, 2)  AS share_novo,
           ROUND(t.sh_pdt, 2)   AS share_pdt,
           ROUND(t.sh_up, 2)    AS share_up
    FROM totals t
    JOIN dim_municipio m USING (cd_municipio_tse)
    LEFT JOIN dim_local_votacao l
      ON l.ano_eletivo = 2022 AND l.cd_municipio_tse = t.cd_municipio_tse
     AND l.nr_zona = t.nr_zona AND l.nr_local_votacao = t.nr_local_votacao
    ORDER BY t.cd_municipio_tse, t.nr_zona, t.nr_local_votacao
) TO 'D:/Dados_TSE/data/analise/mapa_voto_local_2022.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');