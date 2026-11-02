/* ---------------------------------------------------------------------------
   QUERY : q11_decil_abstencao_x_perfil.sql
   OBJETIVO : como o perfil socioeleitoral da SECAO varia com o decil (10%)
              de abstencao. Rodar para 2022 (GOVERNADOR) e 2024 (PREFEITO).
   BASE : vw_abstencao_secao (q08) + vw_perfil_secao (q09)
   NOTA  : cd_tipo_secao_agregada = 1 'Principal' (a que recebe votos),
           2 'Agregada' (absorvida, sem votos) -> excluir 2.
--------------------------------------------------------------------------- */
WITH base AS (
    SELECT a.ab_pct, p.total, p.s_60_69, p.s_70mais, p.sup_completo, p.baixa_esc
    FROM vw_abstencao_secao a
    JOIN vw_perfil_secao p
      ON p.ano_eletivo = a.ano_eletivo AND p.cd_municipio_tse = a.cd_municipio_tse
     AND p.nr_zona = a.nr_zona AND p.nr_secao = a.nr_secao
    LEFT JOIN dim_secao s
      ON s.ano_eletivo = a.ano_eletivo AND s.cd_municipio_tse = a.cd_municipio_tse
     AND s.nr_zona = a.nr_zona AND s.nr_secao = a.nr_secao
    WHERE a.ano_eletivo = 2022          -- trocar para 2024 (PREFEITO)
      AND a.ab_pct BETWEEN 0 AND 70
      AND COALESCE(s.cd_tipo_secao_agregada, 0) <> 2
),
decis AS (
    SELECT NTILE(10) OVER (ORDER BY ab_pct) AS decil,
           ab_pct, total, s_60_69, s_70mais, sup_completo, baixa_esc
    FROM base
)
SELECT decil,
       COUNT(*)                                AS n_secoes,
       ROUND(AVG(ab_pct), 2)                   AS ab_medio,
       ROUND(100.0 * SUM(s_60_69)      / SUM(total), 2) AS pct_60_69,
       ROUND(100.0 * SUM(s_70mais)     / SUM(total), 2) AS pct_70mais,
       ROUND(100.0 * SUM(sup_completo) / SUM(total), 2) AS pct_sup_completo,
       ROUND(100.0 * SUM(baixa_esc)    / SUM(total), 2) AS pct_baixa_esc
FROM decis
GROUP BY decil
ORDER BY decil;