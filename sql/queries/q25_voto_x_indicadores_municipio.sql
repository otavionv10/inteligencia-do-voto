/* ---------------------------------------------------------------------------
   QUERY : q25_voto_x_indicadores_municipio.sql
   OBJETIVO : base para grafico de dispersao (scatter) com regressao - cruza
              % de voto por campo (Presidente 2022 2T e Dep.Federal 2022) com
              indicadores socioeconomicos do IBGE, por municipio de SP.
   FONTE   : dim_municipio enriquecido (enrich_ibge.py) + campo_{presidente,
             depfederal}_2022_por_municipio.csv (ja existentes, sem coleta nova).
   SAIDA   : data/analise/voto_x_indicadores_municipio_2022.csv
--------------------------------------------------------------------------- */
COPY (
    WITH pres AS (
        SELECT cd_municipio_tse, share_dir AS pres_dir, share_esq AS pres_esq
        FROM read_csv('D:/Dados_TSE/data/analise/campo_presidente_2022_por_municipio.csv',
                       delim=';', header=true)
        WHERE nr_turno = 2
    ),
    dep AS (
        SELECT cd_municipio_tse, share_dir AS dep_dir, share_cen AS dep_cen, share_esq AS dep_esq
        FROM read_csv('D:/Dados_TSE/data/analise/campo_depfederal_2022_por_municipio.csv',
                       delim=';', header=true)
        WHERE nr_turno = 1
    )
    SELECT m.cd_municipio_tse, m.nm_municipio_tse,
           m.ibge_pop_2022, ROUND(m.ibge_dens_2022, 1) AS dens_hab_km2,
           m.ibge_pib_pc_2023, m.ibge_idhm_2010, m.ibge_idhm_educacao_2010,
           m.ibge_idhm_renda_2010,
           p.pres_dir, p.pres_esq, d.dep_dir, d.dep_cen, d.dep_esq
    FROM dim_municipio m
    JOIN pres p USING (cd_municipio_tse)
    JOIN dep d USING (cd_municipio_tse)
    WHERE m.sg_uf = 'SP'
    ORDER BY m.nm_municipio_tse
) TO 'D:/Dados_TSE/data/analise/voto_x_indicadores_municipio_2022.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');
