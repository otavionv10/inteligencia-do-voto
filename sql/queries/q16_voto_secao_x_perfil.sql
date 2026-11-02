/* ---------------------------------------------------------------------------
   QUERY : q16_voto_secao_x_perfil.sql
   OBJETIVO : segregacao socioespacial do voto: share Tarcisio/Haddad por SECAO
              x perfil demografico da MESMA secao (2022 Governador 1T).
   BASE : vw_abstencao_secao (aptos/cmp), vw_perfil_secao, fact_votacao_secao.
--------------------------------------------------------------------------- */
WITH vot AS (
    SELECT cd_municipio_tse, nr_zona, nr_secao,
           100.0 * SUM(CASE WHEN nr_votavel=10 THEN qt_votos END)
                 / NULLIF(SUM(CASE WHEN nr_votavel NOT IN (95,96,97) THEN qt_votos END),0) AS sh_rep,
           100.0 * SUM(CASE WHEN nr_votavel=13 THEN qt_votos END)
                 / NULLIF(SUM(CASE WHEN nr_votavel NOT IN (95,96,97) THEN qt_votos END),0) AS sh_pt
    FROM fact_votacao_secao
    WHERE ano_eletivo = 2022 AND nr_turno = 1 AND UPPER(ds_cargo) = 'GOVERNADOR'
    GROUP BY 1,2,3
),
base AS (
    SELECT v.sh_rep, v.sh_pt, p.total, p.s_60_69, p.s_70mais, p.sup_completo, p.baixa_esc
    FROM vot v
    JOIN vw_abstencao_secao a
      ON a.ano_eletivo=2022 AND a.cd_municipio_tse=v.cd_municipio_tse
     AND a.nr_zona=v.nr_zona AND a.nr_secao=v.nr_secao
    JOIN vw_perfil_secao p
      ON p.ano_eletivo=2022 AND p.cd_municipio_tse=v.cd_municipio_tse
     AND p.nr_zona=v.nr_zona AND p.nr_secao=v.nr_secao
    LEFT JOIN dim_secao s
      ON s.ano_eletivo=2022 AND s.cd_municipio_tse=v.cd_municipio_tse
     AND s.nr_zona=v.nr_zona AND s.nr_secao=v.nr_secao
    WHERE a.ab_pct BETWEEN 0 AND 70 AND COALESCE(s.cd_tipo_secao_agregada,0) <> 2
)
SELECT ROUND(CORR(sh_rep, 100.0*s_70mais/total), 3) AS r_rep_70mais,
       ROUND(CORR(sh_rep, 100.0*s_60_69/total), 3)  AS r_rep_60_69,
       ROUND(CORR(sh_rep, 100.0*sup_completo/total),3) AS r_rep_sup,
       ROUND(CORR(sh_rep, 100.0*baixa_esc/total), 3) AS r_rep_baixa,
       COUNT(*) AS n_secoes
FROM base;