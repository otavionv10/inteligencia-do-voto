/* ---------------------------------------------------------------------------
   QUERY : q15_geografia_municipios.sql
   OBJETIVO : camada geografica por municipio, pronta para mapa (QGIS/kepler) -
              centroide lat/lon (media dos locais de votacao 2022), indicadores
              IBGE e variaveis eleitorais (abstencao, share de voto 2022/2024).
   NOTA   : TSE nao publica vinculo secao->local; centroide = media dos locais
              de votacao do municipio (aproxima centro urbano).
   SAIDA  : data/analise/geografia_por_municipio.csv
--------------------------------------------------------------------------- */
COPY (
    WITH geo AS (
        SELECT cd_municipio_tse,
               AVG(nr_latitude)  AS lat,
               AVG(nr_longitude) AS lon,
               COUNT(*)          AS n_locais
        FROM dim_local_votacao
        WHERE ano_eletivo = 2022 AND nr_latitude IS NOT NULL AND nr_longitude IS NOT NULL
        GROUP BY 1
    ),
    ab AS (
        SELECT cd_municipio_tse,
               100.0 * (1 - SUM(comparecimento) / SUM(aptos)) AS ab_pct
        FROM vw_abstencao_secao
        WHERE ano_eletivo = 2022 AND ab_pct BETWEEN 0 AND 70
        GROUP BY 1
    ),
    v22 AS (
        SELECT v.cd_municipio_tse,
               100.0 * SUM(CASE WHEN v.nr_votavel=10 THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END),0) AS sh_rep_22,
               100.0 * SUM(CASE WHEN v.nr_votavel=13 THEN v.qt_votos END)
                     / NULLIF(SUM(CASE WHEN v.nr_votavel NOT IN (95,96,97) THEN v.qt_votos END),0) AS sh_pt_22
        FROM fact_votacao_secao v
        WHERE v.ano_eletivo=2022 AND v.nr_turno=1 AND UPPER(v.ds_cargo)='GOVERNADOR'
        GROUP BY 1
    )
    SELECT m.cd_municipio_ibge,
           CASE WHEN m.cd_municipio_tse='71072' THEN m.nm_municipio_tse || ' (capital)' ELSE m.nm_municipio_tse END AS nm_municipio,
           m.sg_uf,
           g.lat, g.lon, g.n_locais,
           m.ibge_pop_2022, m.ibge_area_km2, m.ibge_dens_2022,
           m.ibge_pib_pc_2023, m.ibge_idhm_2010, m.ibge_idhm_renda_2010,
           ROUND(ab.ab_pct, 2)  AS ab_pct_2022,
           ROUND(v.sh_rep_22, 2) AS share_rep_2022,
           ROUND(v.sh_pt_22, 2)  AS share_pt_2022
    FROM dim_municipio m
    LEFT JOIN geo g  USING (cd_municipio_tse)
    LEFT JOIN ab     USING (cd_municipio_tse)
    LEFT JOIN v22 v  USING (cd_municipio_tse)
    WHERE m.sg_uf = 'SP'
    ORDER BY m.nm_municipio_tse
) TO 'D:/Dados_TSE/data/analise/geografia_por_municipio.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');