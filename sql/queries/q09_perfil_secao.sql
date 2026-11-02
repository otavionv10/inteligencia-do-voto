/* ---------------------------------------------------------------------------
   QUERY : q09_perfil_secao.sql
   OBJETIVO : shares demograficos por secao (a partir de fact_eleitorado_perfil)
              FEMININO | 60-69 anos (voto obrigatorio) | 70+ anos (facultativo)
              | SUPERIOR COMPLETO | baixa escolaridade
   NOTA : cor/raca no perfil por secao vem todo '#NE' (nao usar).
--------------------------------------------------------------------------- */
CREATE OR REPLACE VIEW vw_perfil_secao AS
SELECT ano_eletivo, cd_municipio_tse, nr_zona, nr_secao,
       SUM(qt_eleitores_perfil) AS total,
       SUM(CASE WHEN TRIM(ds_genero)='FEMININO' THEN qt_eleitores_perfil END) AS feminino,
       SUM(CASE WHEN TRIM(ds_faixa_etaria) IN
               ('60 a 64 anos','65 a 69 anos')
            THEN qt_eleitores_perfil END) AS s_60_69,
       SUM(CASE WHEN TRIM(ds_faixa_etaria) IN
               ('70 a 74 anos','75 a 79 anos','80 a 84 anos','85 a 89 anos',
                '90 a 94 anos','95 a 99 anos','100 anos ou mais')
            THEN qt_eleitores_perfil END) AS s_70mais,
       SUM(CASE WHEN TRIM(ds_grau_escolaridade)='SUPERIOR COMPLETO'
            THEN qt_eleitores_perfil END) AS sup_completo,
       SUM(CASE WHEN TRIM(ds_grau_escolaridade) IN
               ('ANALFABETO','ENSINO FUNDAMENTAL INCOMPLETO')
            THEN qt_eleitores_perfil END) AS baixa_esc
FROM fact_eleitorado_perfil
WHERE ano_eletivo IN (2022, 2024)
GROUP BY 1,2,3,4;

/* Percentuais por secao */
SELECT p.ano_eletivo, p.cd_municipio_tse, p.nr_zona, p.nr_secao, p.total,
       100.0 * p.feminino       / p.total AS pct_feminino,
       100.0 * p.s_60_69        / p.total AS pct_60_69,
       100.0 * p.s_70mais       / p.total AS pct_70mais,
       100.0 * p.sup_completo   / p.total AS pct_sup_completo,
       100.0 * p.baixa_esc      / p.total AS pct_baixa_esc
FROM vw_perfil_secao p
WHERE p.total > 0;