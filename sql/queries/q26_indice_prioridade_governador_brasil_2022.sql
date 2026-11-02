/* ---------------------------------------------------------------------------
   QUERY : q26_indice_prioridade_governador_brasil_2022.sql
   OBJETIVO : Indice de Prioridade de campanha por LOCAL de votacao -
              GOVERNADOR BRASIL 2022, turno DECISIVO por UF (2T se o estado
              teve 2º turno, senao 1T). Versao nacional do q21 (que era fixo
              em SP: Tarcisio 10 x Haddad 13) - aqui a classificacao de campo
              vem dos PARTIDOS (vw_candidato_campo + dim_campo_partido),
              igual ao mapa nacional por local (gerar_mapa_local_nacional.py,
              turno_decisivo_governador) e ao q22 (depfederal).
   METRICA  : gap_pct_aptos = |votos_dir - votos_esq| / aptos_do_local * 100.
   FONTES   : fact_votacao_secao, fact_eleitorado_local (aptos, 2022),
              dim_local_votacao, dim_municipio, vw_candidato_campo,
              dim_campo_partido.
   LIMPEZA  : exclui secao 'Agregada' (cd_tipo_secao_agregada=2) do aptos;
              abstencao_pct fora de [0,70] vira NULL.
   LIMIAR   : abstencao 25% e forca 30/60% - heuristicas ajustaveis (ver q20).
   SAIDA    : data/analise/indice_prioridade_governador_2022.csv
   Criado   : 2026-09-28
--------------------------------------------------------------------------- */
COPY (
    WITH turno_uf AS (
        SELECT m.sg_uf, MAX(v.nr_turno) AS turno
        FROM fact_votacao_secao v
        JOIN dim_municipio m USING (cd_municipio_tse)
        WHERE v.ano_eletivo = 2022 AND UPPER(v.ds_cargo) = 'GOVERNADOR'
        GROUP BY 1
    ),
    votos AS (
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               COALESCE(SUM(v.qt_votos) FILTER (WHERE COALESCE(c1.campo, c2.campo, p.campo) = 'ESQUERDA'),0) AS vot_esq,
               COALESCE(SUM(v.qt_votos) FILTER (WHERE COALESCE(c1.campo, c2.campo, p.campo) = 'CENTRO'),0)   AS vot_cen,
               COALESCE(SUM(v.qt_votos) FILTER (WHERE COALESCE(c1.campo, c2.campo, p.campo) = 'DIREITA'),0)  AS vot_dir,
               SUM(v.qt_votos) AS comparecimento,
               SUM(CASE WHEN v.nr_votavel NOT IN (95,96) THEN v.qt_votos END) AS validos
        FROM fact_votacao_secao v
        JOIN dim_municipio m USING (cd_municipio_tse)
        JOIN turno_uf t ON t.sg_uf = m.sg_uf AND t.turno = v.nr_turno
        LEFT JOIN vw_candidato_campo c1
               ON c1.ano_eletivo = v.ano_eletivo AND c1.sq_candidato = v.sq_candidato
        LEFT JOIN vw_candidato_campo c2
               ON c2.ano_eletivo = v.ano_eletivo
              AND c2.nr_candidato = v.nr_votavel
              AND UPPER(c2.ds_cargo) = UPPER(v.ds_cargo)
              AND c2.sg_uf = COALESCE(m.sg_uf, '--')
        LEFT JOIN dim_campo_partido p
               ON p.nr_partido = v.nr_votavel AND COALESCE(v.sq_candidato, -1) < 0
        WHERE v.ano_eletivo = 2022 AND UPPER(v.ds_cargo) = 'GOVERNADOR'
        GROUP BY 1,2,3
    ),
    aptos AS (
        SELECT f.cd_municipio_tse, f.nr_zona, f.nr_local_votacao,
               SUM(f.qt_eleitor_secao) AS aptos
        FROM fact_eleitorado_local f
        JOIN dim_municipio m USING (cd_municipio_tse)
        JOIN turno_uf t ON t.sg_uf = m.sg_uf AND t.turno = f.nr_turno
        LEFT JOIN dim_secao s
               ON s.ano_eletivo = f.ano_eletivo AND s.cd_municipio_tse = f.cd_municipio_tse
              AND s.nr_zona = f.nr_zona AND s.nr_secao = f.nr_secao
        WHERE f.ano_eletivo = 2022
          AND COALESCE(s.cd_tipo_secao_agregada, 0) <> 2
        GROUP BY 1,2,3
    ),
    base AS (
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               v.vot_esq, v.vot_cen, v.vot_dir, v.comparecimento, v.validos, a.aptos,
               100.0 * v.vot_esq / NULLIF(v.validos,0) AS share_esq,
               100.0 * v.vot_cen / NULLIF(v.validos,0) AS share_cen,
               100.0 * v.vot_dir / NULLIF(v.validos,0) AS share_dir,
               CASE WHEN 100.0 * (1 - v.comparecimento / NULLIF(a.aptos,0)) BETWEEN 0 AND 70
                    THEN 100.0 * (1 - v.comparecimento / NULLIF(a.aptos,0)) END AS abstencao_pct
        FROM votos v
        LEFT JOIN aptos a USING (cd_municipio_tse, nr_zona, nr_local_votacao)
    )
    SELECT b.cd_municipio_tse, m.nm_municipio_tse, b.nr_zona, b.nr_local_votacao,
           l.nm_local_votacao, l.ds_tipo_local, l.nr_latitude AS lat, l.nr_longitude AS lon,
           b.aptos, b.comparecimento, b.validos,
           b.vot_esq, b.vot_cen, b.vot_dir,
           ROUND(b.share_esq, 2) AS share_esq,
           ROUND(b.share_cen, 2) AS share_cen,
           ROUND(b.share_dir, 2) AS share_dir,
           ROUND(b.share_dir - b.share_esq, 2) AS margem_pp,
           ROUND(100.0 * ABS(b.vot_dir - b.vot_esq) / NULLIF(b.aptos,0), 2) AS gap_pct_aptos,
           ROUND(b.abstencao_pct, 2) AS abstencao_pct,
           CASE WHEN COALESCE(b.vot_dir,0) >= COALESCE(b.vot_esq,0)
                 AND COALESCE(b.vot_dir,0) >= COALESCE(b.vot_cen,0) THEN 'DIREITA'
                WHEN COALESCE(b.vot_cen,0) >= COALESCE(b.vot_esq,0) THEN 'CENTRO'
                ELSE 'ESQUERDA' END AS vencedor_campo,
           CASE WHEN COALESCE(b.vot_dir,0) >= COALESCE(b.vot_esq,0) THEN 'DIREITA'
                ELSE 'ESQUERDA' END AS vencedor,
           CASE
             WHEN b.share_dir <= 30 THEN 'HOSTIL'
             WHEN b.share_dir >= 60
               THEN CASE WHEN b.abstencao_pct > 25 THEN 'MOBILIZACAO' ELSE 'BASE_CONSOLIDADA' END
             ELSE CASE WHEN b.abstencao_pct > 25 THEN 'PERSUASAO_MOBILIZACAO' ELSE 'PERSUASAO' END
           END AS quadrante_direita,
           CASE
             WHEN b.share_esq <= 30 THEN 'HOSTIL'
             WHEN b.share_esq >= 60
               THEN CASE WHEN b.abstencao_pct > 25 THEN 'MOBILIZACAO' ELSE 'BASE_CONSOLIDADA' END
             ELSE CASE WHEN b.abstencao_pct > 25 THEN 'PERSUASAO_MOBILIZACAO' ELSE 'PERSUASAO' END
           END AS quadrante_esquerda
    FROM base b
    JOIN dim_municipio m USING (cd_municipio_tse)
    LEFT JOIN dim_local_votacao l
      ON l.ano_eletivo = 2022 AND l.cd_municipio_tse = b.cd_municipio_tse
     AND l.nr_zona = b.nr_zona AND l.nr_local_votacao = b.nr_local_votacao
    ORDER BY gap_pct_aptos ASC
) TO 'D:/Dados_TSE/data/analise/indice_prioridade_governador_2022.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');
