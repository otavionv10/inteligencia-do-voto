/* ---------------------------------------------------------------------------
   QUERY : q24_trajetoria_presidente_2014_2022.sql
   OBJETIVO : Trajetoria de voto por LOCAL entre as 3 eleicoes presidenciais
              (2014, 2018, 2022 - 2º turno, mesmo enquadramento binario DIR x ESQ)
              -> agrupa locais em PERFIS de comportamento (nao clustering
              estatistico, regras interpretaveis) pra construir uma rede de
              "quem se move parecido", mesmo estando longe geograficamente.
   PERFIS (baseado em swing1=share_dir_18-share_dir_14, swing2=share_dir_22-share_dir_18,
           total=share_dir_22-share_dir_14):
     - MOVEU_FORTE_DIREITA   : total >= +15pp
     - MOVEU_MOD_DIREITA     : total entre +5 e +15pp
     - ESTAVEL_DIREITA       : |total| < 5pp e share_dir_22 > 50
     - ESTAVEL_ESQUERDA      : |total| < 5pp e share_dir_22 <= 50
     - MOVEU_MOD_ESQUERDA    : total entre -15 e -5pp
     - MOVEU_FORTE_ESQUERDA  : total <= -15pp
     - OSCILOU               : swing1 e swing2 com sinais OPOSTOS e ambos > 8pp
                                em modulo (foi numa direcao e voltou - nao e
                                so ruido, filtro de magnitude evita over-flag)
   FONTES  : campo_presidente_{2014,2018,2022}_por_local.csv (gerar_campo_presidente.py
             --nivel local) - ja validado (share_dir 2022 bate 100% com indice_prioridade,
             diferenca maxima 0.0 testada). INNER JOIN => so locais presentes nos 3 anos
             (local novo/fechado entre eleicoes fica de fora, esperado).
   LACUNA DE DADO (achada ao construir esta query): dim_local_votacao so tem coordenada
   p/ 2022/2024/2026 (TSE nao publica lat/lon por local em anos anteriores - mesma lacuna
   ja documentada em fact_eleitorado_local/fact_eleitorado_perfil). Os arquivos "por_local"
   de 2014/2018 ficam com lat/lon NULL por causa disso. Como o CODIGO do local
   (municipio,zona,local) normalmente e o mesmo predio fisico ao longo dos anos, uso a
   coordenada de 2022 como referencia geografica pros 3 anos (aproximacao razoavel,
   nao e um dado novo que falte gerar - e limite real do que o TSE publicou).
   SAIDA   : data/analise/trajetoria_presidente_2014_2022.csv
--------------------------------------------------------------------------- */
COPY (
    WITH y14 AS (
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               share_dir AS shdir_14, validos AS validos_14
        FROM read_csv('D:/Dados_TSE/data/analise/campo_presidente_2014_por_local.csv',
                       delim=';', header=true)
        WHERE nr_turno = 2
    ),
    y18 AS (
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               share_dir AS shdir_18, validos AS validos_18
        FROM read_csv('D:/Dados_TSE/data/analise/campo_presidente_2018_por_local.csv',
                       delim=';', header=true)
        WHERE nr_turno = 2
    ),
    y22 AS (
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               nm_municipio_tse, nm_local_votacao, ds_tipo_local, lat, lon,
               share_dir AS shdir_22, validos AS validos_22
        FROM read_csv('D:/Dados_TSE/data/analise/campo_presidente_2022_por_local.csv',
                       delim=';', header=true)
        WHERE nr_turno = 2
    ),
    base AS (
        SELECT c.cd_municipio_tse, c.nr_zona, c.nr_local_votacao,
               c.nm_municipio_tse, c.nm_local_votacao, c.ds_tipo_local, c.lat, c.lon,
               a.validos_14, b.validos_18, c.validos_22,
               a.shdir_14, b.shdir_18, c.shdir_22,
               ROUND(b.shdir_18 - a.shdir_14, 2) AS swing1,
               ROUND(c.shdir_22 - b.shdir_18, 2) AS swing2,
               ROUND(c.shdir_22 - a.shdir_14, 2) AS total
        FROM y14 a
        JOIN y18 b USING (cd_municipio_tse, nr_zona, nr_local_votacao)
        JOIN y22 c USING (cd_municipio_tse, nr_zona, nr_local_votacao)
        WHERE c.lat IS NOT NULL
    )
    SELECT *,
           CASE
             WHEN SIGN(swing1) <> 0 AND SIGN(swing2) <> 0 AND SIGN(swing1) <> SIGN(swing2)
                  AND ABS(swing1) > 8 AND ABS(swing2) > 8 THEN 'OSCILOU'
             WHEN total >= 15 THEN 'MOVEU_FORTE_DIREITA'
             WHEN total >= 5 THEN 'MOVEU_MOD_DIREITA'
             WHEN total <= -15 THEN 'MOVEU_FORTE_ESQUERDA'
             WHEN total <= -5 THEN 'MOVEU_MOD_ESQUERDA'
             WHEN shdir_22 > 50 THEN 'ESTAVEL_DIREITA'
             ELSE 'ESTAVEL_ESQUERDA'
           END AS perfil
    FROM base
    ORDER BY total DESC
) TO 'D:/Dados_TSE/data/analise/trajetoria_presidente_2014_2022.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');
