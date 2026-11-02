/* ---------------------------------------------------------------------------
   QUERY : q19_campo_presidente_2022.sql
   OBJETIVO : shares por CAMPO POLITICO (ESQUERDA/CENTRO/DIREITA) para
              Presidente 2022 (SP) por municipio / zona / secao.
              campo vem de dim_candidato_map via sq_candidato (nominal);
              legenda/branco/nulo mapeado por nr_votavel/dim_partido.
   SAIDAS : data/analise/campo_presidente_2022_por_{municipio,zona,secao}.csv
   REGRA  : vencedor_campo = bloco com mais votos validos; share sobre validos
            (NOMINAL+LEGENDA; exclui 95/96). 1 registro por turno.
            Via agg_voto_municipio_partido (camada analítica v006).
   USO    : _scripts/gerar_campo_presidente.py gera os 3 CSVs (equiv. a este SQL).
--------------------------------------------------------------------------- */

-- 1) TOP por municipio (ex.: cidades com maior share de DIREITA no 2T)
WITH c AS (
    SELECT ano_eletivo, nr_turno, cd_municipio_tse, campo, votos, validos
      FROM agg_voto_municipio_partido
     WHERE cargo='PRESIDENTE'
), rank_campo AS (
    SELECT c.nr_turno, m.nm_municipio_tse,
           c.vot_esq, 100.0*c.vot_esq/c.validos AS share_esq,
           c.vot_dir, 100.0*c.vot_dir/c.validos AS share_dir,
           c.vot_cen, 100.0*c.vot_cen/c.validos AS share_cen,
           c.validos
      FROM (SELECT cd_municipio_tse, nr_turno,
                   COALESCE(SUM(CASE WHEN campo='ESQUERDA' THEN votos END),0) vot_esq,
                   COALESCE(SUM(CASE WHEN campo='CENTRO'   THEN votos END),0) vot_cen,
                   COALESCE(SUM(CASE WHEN campo='DIREITA'  THEN votos END),0) vot_dir,
                   MAX(validos) validos
              FROM c GROUP BY 1,2) c
      JOIN dim_municipio m USING (cd_municipio_tse)
     WHERE c.nr_turno = 2
)
SELECT * FROM rank_campo ORDER BY share_dir DESC, nm_municipio_tse LIMIT 20;

-- 2) Contagem de cidades por vencedor de campo (2T) -> esperado DIR 547 /
--    ESQ 97 / EMPATE 1
WITH c AS (
    SELECT cd_municipio_tse, nr_turno, campo, votos
      FROM agg_voto_municipio_partido
     WHERE cargo='PRESIDENTE'
), por_cidade AS (
    SELECT cd_municipio_tse,
           COALESCE(SUM(CASE WHEN campo='ESQUERDA' THEN votos END),0) vot_esq,
           COALESCE(SUM(CASE WHEN campo='CENTRO'   THEN votos END),0) vot_cen,
           COALESCE(SUM(CASE WHEN campo='DIREITA'  THEN votos END),0) vot_dir
      FROM c WHERE nr_turno=2
     GROUP BY 1
)
SELECT CASE WHEN vot_dir > vot_esq AND vot_dir > vot_cen THEN 'DIREITA'
            WHEN vot_esq > vot_dir AND vot_esq > vot_cen THEN 'ESQUERDA'
            WHEN vot_cen > vot_dir AND vot_cen > vot_esq THEN 'CENTRO'
            ELSE 'EMPATE' END AS vencedor_campo, COUNT(*) AS cidades
  FROM por_cidade
 GROUP BY 1 ORDER BY 1;