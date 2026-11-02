/* ---------------------------------------------------------------------------
   QUERY : q23_rachadura_voto_2022.sql
   OBJETIVO : "Rachadura de voto" (ticket-splitting) por LOCAL - cruza o vencedor
              de 3 cargos na mesma eleicao 2022 (Presidente 2T, Governador 2T,
              Deputado Federal por campo) pra achar locais onde o eleitorado
              muda de lado dependendo do cargo. Mais forte que margem apertada
              isolada: um local 50/50 que vota igual em tudo pode ser so um
              bairro dividido entre 2 grupos fieis; um local que troca de
              vencedor entre cargos PROVA que aquela populacao e persuasivel.
   CATEGORIAS:
     - CONSISTENTE_DIREITA / CONSISTENTE_ESQUERDA : os 3 cargos concordam
     - RACHADO_EXECUTIVO  : Presidente e Governador (ambos binarios, mesmo
                            enquadramento nacional) tem vencedores DIFERENTES
                            - sinal mais forte e mais limpo de rachadura
     - RACHADO_LEGISLATIVO: Presidente/Governador concordam, mas no Deputado
                            Federal o LADO OPOSTO tem share_dir/share_esq
                            maior que o lado do executivo - rachadura real,
                            nao so fragmentacao (compara os shares, nao so
                            o vencedor_campo nominal - ver FRAGMENTACAO abaixo)
     - FRAGMENTACAO_DIREITA/ESQUERDA: Deputado Federal teve CENTRO como
                            vencedor nominal (plural), mas o lado do executivo
                            ainda tem share MAIOR que o lado oposto ali -
                            e so o voto de direita (ou esquerda) se espalhando
                            entre muitos candidatos/partidos, NAO indica
                            eleitor mudando de lado (proporcional multipartidario
                            fragmenta o campo grande, ninguem vira maioria sozinho).
                            Distinguir isso do RACHADO_LEGISLATIVO evita ler
                            fragmentacao de voto como se fosse persuasao real.
   FONTES  : dado 100% derivado dos CSVs ja validados de q20/q21/q22 (nao
             reconsulta fact_votacao_secao do zero - evita duplicar a logica
             de aptos/validos ja testada).
   METRICA : dissonancia_pct = maior share_dir - menor share_dir entre os 3
             cargos - capta rachadura PARCIAL tambem (mesmo vencedor, mas
             intensidade bem diferente), nao so a troca categorica de lado.
   SAIDA   : data/analise/rachadura_voto_2022.csv
--------------------------------------------------------------------------- */
COPY (
    WITH pres AS (
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               nm_municipio_tse, nm_local_votacao, ds_tipo_local, lat, lon,
               validos AS validos_pres, share_dir AS shdir_pres, share_esq AS shesq_pres,
               vencedor AS venc_pres
        FROM read_csv('D:/Dados_TSE/data/analise/indice_prioridade_presidente_2022.csv',
                       delim=';', header=true)
    ),
    gov AS (
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               validos AS validos_gov, share_dir AS shdir_gov, share_esq AS shesq_gov,
               vencedor AS venc_gov
        FROM read_csv('D:/Dados_TSE/data/analise/indice_prioridade_governador_2022.csv',
                       delim=';', header=true)
    ),
    depfed AS (
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               validos AS validos_depfed, share_dir AS shdir_depfed, share_esq AS shesq_depfed,
               vencedor_campo AS venc_depfed
        FROM read_csv('D:/Dados_TSE/data/analise/indice_prioridade_depfederal_2022.csv',
                       delim=';', header=true)
    )
    SELECT p.cd_municipio_tse, p.nm_municipio_tse, p.nr_zona, p.nr_local_votacao,
           p.nm_local_votacao, p.ds_tipo_local, p.lat, p.lon,
           p.validos_pres, p.shdir_pres, p.venc_pres,
           g.validos_gov, g.shdir_gov, g.venc_gov,
           d.validos_depfed, d.shdir_depfed, d.shesq_depfed, d.venc_depfed,
           ROUND(GREATEST(p.shdir_pres, g.shdir_gov, COALESCE(d.shdir_depfed, p.shdir_pres))
               - LEAST(p.shdir_pres, g.shdir_gov, COALESCE(d.shdir_depfed, p.shdir_pres)), 2) AS dissonancia_pct,
           CASE
             WHEN p.venc_pres <> g.venc_gov THEN 'RACHADO_EXECUTIVO'
             WHEN p.venc_pres = 'DIREITA' AND d.shesq_depfed > d.shdir_depfed THEN 'RACHADO_LEGISLATIVO'
             WHEN p.venc_pres = 'ESQUERDA' AND d.shdir_depfed > d.shesq_depfed THEN 'RACHADO_LEGISLATIVO'
             WHEN d.venc_depfed = 'CENTRO' THEN 'FRAGMENTACAO_' || p.venc_pres
             WHEN p.venc_pres = 'DIREITA' THEN 'CONSISTENTE_DIREITA'
             ELSE 'CONSISTENTE_ESQUERDA'
           END AS categoria
    FROM pres p
    JOIN gov g USING (cd_municipio_tse, nr_zona, nr_local_votacao)
    LEFT JOIN depfed d USING (cd_municipio_tse, nr_zona, nr_local_votacao)
    WHERE p.lat IS NOT NULL
    ORDER BY dissonancia_pct DESC
) TO 'D:/Dados_TSE/data/analise/rachadura_voto_2022.csv'
  (FORMAT CSV, HEADER, DELIMITER ';');
