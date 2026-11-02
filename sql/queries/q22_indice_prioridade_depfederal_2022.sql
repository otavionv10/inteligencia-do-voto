/* ---------------------------------------------------------------------------
   QUERY : q22_indice_prioridade_depfederal_2022.sql
   OBJETIVO : Indice de Prioridade de campanha por LOCAL de votacao - Deputado
              Federal SP 2022 (1 turno so, multipartidario -> usa CAMPO
              ESQUERDA/CENTRO/DIREITA via dim_campo_partido, mesmo join de
              gerar_campo_deputado_federal.py, nao reescrito do zero).
              margem/gap usam so DIREITA x ESQUERDA (CENTRO fica de fora do
              calculo, e contexto) - mesmo criterio ja usado no filtro
              Ambos/Direita/Esquerda dos mapas do site (sem opcao Centro).
   METRICA  : gap_pct_aptos = |votos_dir - votos_esq| / aptos_do_local * 100.
   FONTES   : fact_votacao_secao, dim_candidato + dim_campo_partido + dim_partido
              (classificacao de campo), fact_eleitorado_local (aptos, 2022),
              dim_local_votacao (chave com nr_zona, fix ADR-008/v027).
   LIMPEZA  : mesma de q20/q21 - exclui secao 'Agregada' do aptos; abstencao_pct
              fora de [0,70] vira NULL.
   LIMIAR   : abstencao 25% e forca 30/60% - heuristicas ajustaveis (ver q20).
   SAIDA    : data/analise/indice_prioridade_depfederal_2022.csv
--------------------------------------------------------------------------- */
COPY (
    WITH cand AS (
        SELECT c2.ano_eletivo, c2.sq_candidato, p.campo
        FROM (SELECT *, row_number() OVER
                        (PARTITION BY ano_eletivo, sq_candidato
                         ORDER BY nm_candidato) rn
                FROM dim_candidato) c2
        LEFT JOIN dim_campo_partido p ON p.nr_partido = c2.nr_partido
        WHERE c2.rn = 1
    ),
    votos AS (
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               SUM(CASE WHEN COALESCE(k.campo, pt.campo) = 'ESQUERDA' THEN v.qt_votos END) AS vot_esq,
               SUM(CASE WHEN COALESCE(k.campo, pt.campo) = 'CENTRO'   THEN v.qt_votos END) AS vot_cen,
               SUM(CASE WHEN COALESCE(k.campo, pt.campo) = 'DIREITA'  THEN v.qt_votos END) AS vot_dir,
               SUM(v.qt_votos) AS comparecimento,
               SUM(CASE WHEN v.nr_votavel NOT IN (95,96) THEN v.qt_votos END) AS validos
        FROM fact_votacao_secao v
        LEFT JOIN cand k ON k.ano_eletivo = v.ano_eletivo AND k.sq_candidato = v.sq_candidato
        LEFT JOIN dim_partido pt ON pt.nr_partido = v.nr_votavel
        WHERE v.ano_eletivo = 2022 AND v.nr_turno = 1 AND UPPER(v.ds_cargo) = 'DEPUTADO FEDERAL'
        GROUP BY 1,2,3
    ),
    aptos AS (
        SELECT f.cd_municipio_tse, f.nr_zona, f.nr_local_votacao,
               SUM(f.qt_eleitor_secao) AS aptos
        FROM fact_eleitorado_local f
        LEFT JOIN dim_secao s
               ON s.ano_eletivo = f.ano_eletivo AND s.cd_municipio_tse = f.cd_municipio_tse
              AND s.nr_zona = f.nr_zona AND s.nr_secao = f.nr_secao
        WHERE f.ano_eletivo = 2022 AND f.nr_turno = 1
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
) TO 'D:/Dados_TSE/data/analise/indice_prioridade_depfederal_2022.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');
