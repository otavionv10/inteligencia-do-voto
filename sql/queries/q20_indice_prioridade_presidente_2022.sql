/* ---------------------------------------------------------------------------
   QUERY : q20_indice_prioridade_presidente_2022.sql
   OBJETIVO : Indice de Prioridade de campanha por LOCAL de votacao - Presidente
              2022, 2º turno (Lula 13 x Bolsonaro 22 - caso mais limpo, so 2
              candidatos, sem CENTRO). Cruza FORCA do campo (share sobre
              validos) x ABSTENCAO (comparecimento/aptos) para classificar cada
              local em 4 quadrantes de prioridade de campanha:
                - BASE_CONSOLIDADA      : forca >=60% e abstencao baixa (so manter)
                - MOBILIZACAO           : forca >=60% e abstencao alta (GOTV)
                - HOSTIL                : forca <=30% (nao vale investir aqui)
                - PERSUASAO             : forca 30-60% e abstencao baixa (maior
                                          ROI de convencimento)
                - PERSUASAO_MOBILIZACAO : forca 30-60% e abstencao alta (persuadir
                                          + fazer sair de casa)
              Gerado 2x (quadrante_direita, quadrante_esquerda) para servir
              qualquer campanha, igual ao filtro Ambos/Direita/Esquerda dos mapas.
   METRICA  : gap_pct_aptos = |votos_dir - votos_esq| / aptos_do_local * 100
              -> quanto menor, mais perto de virar o local (maior prioridade
              de persuasao). Pondera pelo tamanho real do eleitorado, nao so %.
   FONTES   : fact_votacao_secao (votos), fact_eleitorado_local (aptos, so
              2022/24/26 - TSE nao publica aptos por local em anos anteriores),
              dim_local_votacao (lat/lon - chave com nr_zona, fix ADR-008/v027).
   LIMPEZA  : aptos exclui secoes tipo 'Agregada' (cd_tipo_secao_agregada=2,
              nao recebem voto mas teriam qt_eleitor_secao duplicado se somadas
              junto da secao Principal que as absorve) - mesma regra de q08.
              abstencao_pct fora de [0,70] vira NULL (outlier de merge local<->aptos
              entre turnos - mesmo criterio de outlier ja usado em q08/q10; afeta
              133/10.846 locais = 1,2%). Quadrante usa NULL como "abstencao alta
              nao confirmada" (fallback conservador p/ BASE_CONSOLIDADA/PERSUASAO).
   LIMIAR   : abstencao 25% e forca 30/60% sao heuristicas ajustaveis, nao
              constantes do TSE - revisar com a distribuicao real se necessario.
   SAIDA    : data/analise/indice_prioridade_presidente_2022.csv
--------------------------------------------------------------------------- */
COPY (
    WITH votos AS (
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               SUM(CASE WHEN v.nr_votavel = 13 THEN v.qt_votos END) AS vot_esq,
               SUM(CASE WHEN v.nr_votavel = 22 THEN v.qt_votos END) AS vot_dir,
               SUM(v.qt_votos) AS comparecimento,
               SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END) AS validos
        FROM fact_votacao_secao v
        WHERE v.ano_eletivo = 2022 AND v.nr_turno = 2 AND UPPER(v.ds_cargo) = 'PRESIDENTE'
        GROUP BY 1,2,3
    ),
    aptos AS (
        SELECT f.cd_municipio_tse, f.nr_zona, f.nr_local_votacao,
               SUM(f.qt_eleitor_secao) AS aptos
        FROM fact_eleitorado_local f
        LEFT JOIN dim_secao s
               ON s.ano_eletivo = f.ano_eletivo AND s.cd_municipio_tse = f.cd_municipio_tse
              AND s.nr_zona = f.nr_zona AND s.nr_secao = f.nr_secao
        WHERE f.ano_eletivo = 2022 AND f.nr_turno = 2
          AND COALESCE(s.cd_tipo_secao_agregada, 0) <> 2
        GROUP BY 1,2,3
    ),
    base AS (
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               v.vot_esq, v.vot_dir, v.comparecimento, v.validos, a.aptos,
               100.0 * v.vot_esq / NULLIF(v.validos,0) AS share_esq,
               100.0 * v.vot_dir / NULLIF(v.validos,0) AS share_dir,
               CASE WHEN 100.0 * (1 - v.comparecimento / NULLIF(a.aptos,0)) BETWEEN 0 AND 70
                    THEN 100.0 * (1 - v.comparecimento / NULLIF(a.aptos,0)) END AS abstencao_pct
        FROM votos v
        LEFT JOIN aptos a USING (cd_municipio_tse, nr_zona, nr_local_votacao)
    )
    SELECT b.cd_municipio_tse, m.nm_municipio_tse, b.nr_zona, b.nr_local_votacao,
           l.nm_local_votacao, l.ds_tipo_local, l.nr_latitude AS lat, l.nr_longitude AS lon,
           b.aptos, b.comparecimento, b.validos, b.vot_esq, b.vot_dir,
           ROUND(b.share_esq, 2) AS share_esq,
           ROUND(b.share_dir, 2) AS share_dir,
           ROUND(b.share_dir - b.share_esq, 2) AS margem_pp,
           ROUND(100.0 * ABS(b.vot_dir - b.vot_esq) / NULLIF(b.aptos,0), 2) AS gap_pct_aptos,
           ROUND(b.abstencao_pct, 2) AS abstencao_pct,
           CASE WHEN b.vot_dir > b.vot_esq THEN 'DIREITA' ELSE 'ESQUERDA' END AS vencedor,
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
) TO 'D:/Dados_TSE/data/analise/indice_prioridade_presidente_2022.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');
