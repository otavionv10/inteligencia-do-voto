/* ---------------------------------------------------------------------------
   CAMADA ANALITICA 00 - LIMPEZA DE DUPLICATAS EM dim_candidato
   Problema: dim_candidato contem linhas identicas duplicadas p/ alguns
   candidatos (ex.: FERNANDO HADDAD e TARCISIO, GOV SP 2022). Qualquer
   join por sq_candidato multiplica os votos (ex.: x2).
   Solucao definitiva: reconstruir a tabela com 1 registro por (ano_eletivo,
   sq_candidato), preferindo ds_situacao_candidatura = 'APTO'.
   Idempotente: re-executar nao tem efeito.
--------------------------------------------------------------------------- */

CREATE OR REPLACE TABLE dim_candidato AS
SELECT ano_eletivo, sq_candidato, nr_candidato, nm_candidato, nm_urna_candidato,
       sg_partido, nr_partido, cd_cargo, ds_cargo,
       cd_situacao_candidatura, ds_situacao_candidatura,
       cd_situacao_turno, ds_situacao_turno, sg_uf, cd_genero, ds_genero,
       cd_grau_instrucao, ds_grau_instrucao, cd_estado_civil, ds_estado_civil,
       cd_cor_raca, ds_cor_raca, ds_ocupacao, sg_ue, nm_ue
  FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY ano_eletivo, sq_candidato
               ORDER BY (ds_situacao_candidatura = 'APTO') DESC,
                        ds_situacao_candidatura, nm_candidato
           ) AS rn
      FROM dim_candidato
  )
 WHERE rn = 1;