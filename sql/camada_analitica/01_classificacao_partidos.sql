/* ---------------------------------------------------------------------------
   CAMADA ANALITICA 01 - CLASSIFICACAO CAMPO POLITICO
   Objetivo: definir quem e partido de ESQUERDA/CENTRO/DIREITA.
   Fonte: classificacao convencional do espectro politico brasileiro (manual),
   baseada no posicionamento dos partidos (estudos academicos e praticas).
   NAO existe dado oficial do TSE para isso.
   Direitos de atualizacao: revisar em cada nova eleicao (juncao/renomeacao).
--------------------------------------------------------------------------- */

CREATE OR REPLACE TABLE dim_campo_partido (
    nr_partido INTEGER PRIMARY KEY,
    sg_partido VARCHAR NOT NULL,
    nm_partido VARCHAR NOT NULL,
    campo      VARCHAR NOT NULL CHECK (campo IN ('ESQUERDA', 'CENTRO', 'DIREITA')),
    nota       VARCHAR DEFAULT ''
);

INSERT INTO dim_campo_partido (nr_partido, sg_partido, nm_partido, campo, nota) VALUES
(10, 'REPUBLICANOS', 'Republicanos',                    'DIREITA',  'ex-PRB'),
(11, 'PP',          'Progressistas',                    'DIREITA',  ''),
(12, 'PDT',         'Partido Democratico Trabalhista',  'CENTRO',   'centro-esquerda historica'),
(13, 'PT',          'Partido dos Trabalhadores',        'ESQUERDA', ''),
(14, 'PTB',         'Partido Trabalhista Brasileiro',   'DIREITA',  ''),
(15, 'MDB',         'Movimento Democratico Brasileiro', 'CENTRO',   'ex-PMDB'),
(16, 'PSTU',        'Partido Socialista dos Trabalhadores Unificado', 'ESQUERDA', 'extrema-esquerda'),
(17, 'PSL',         'Partido Social Liberal',           'DIREITA',  'extinto (Uniao Brasil)'),
(18, 'REDE',        'Rede Sustentabilidade',            'ESQUERDA', ''),
(19, 'PODE',        'Podemos',                          'DIREITA',  'ex-PTN'),
(20, 'PODE',        'Podemos (20)',                     'DIREITA',  'lote distinto do TSE'),
(21, 'PCB',         'Partido Comunista Brasileiro',     'ESQUERDA', ''),
(22, 'PL',          'Partido Liberal',                  'DIREITA',  'ex-PR'),
(23, 'CIDADANIA',   'Cidadania',                        'CENTRO',   'ex-PPS'),
(25, 'DEM',         'Democratas',                       'DIREITA',  'extinto (Uniao Brasil)'),
(27, 'DC',          'Democracia Crista',                'DIREITA',  ''),
(28, 'PRTB',        'Partido Renovador Trabalhista Brasileiro', 'DIREITA', ''),
(29, 'PCO',         'Partido da Causa Operaria',        'ESQUERDA', 'extrema-esquerda'),
(30, 'NOVO',        'Partido Novo',                     'DIREITA',  'liberal'),
(31, 'PHS',         'Partido Humanista da Solidariedade', 'DIREITA', ''),
(33, 'MOBILIZA',    'Mobilizacao Nacional',             'DIREITA',  'ex-PMN'),
(35, 'PMB',         'Partido Mulher Brasileira',        'DIREITA',  ''),
(36, 'AGIR',        'Agir',                             'DIREITA',  'ex-PTC'),
(40, 'PSB',         'Partido Socialista Brasileiro',    'CENTRO',   'centro-esquerda'),
(43, 'PV',          'Partido Verde',                    'ESQUERDA', ''),
(44, 'UNIAO',       'Uniao Brasil',                     'DIREITA',  'fusao DEM + PSL'),
(45, 'PSDB',        'Partido da Social Democracia Brasileira', 'DIREITA', 'centro-direita'),
(50, 'PSOL',        'Partido Socialismo e Liberdade',   'ESQUERDA', ''),
(51, 'PATRIOTA',    'Patriota',                         'DIREITA',  ''),
(54, 'PPL',         'Partido Patria Livre',             'ESQUERDA', ''),
(55, 'PSD',         'Partido Social Democratico',       'DIREITA',  'centro'),
(65, 'PC do B',     'Partido Comunista do Brasil',      'ESQUERDA', ''),
(70, 'AVANTE',      'Avante',                           'CENTRO',   'ex-PT do B'),
(77, 'SD',          'Solidariedade',                    'CENTRO',   ''),
(80, 'UP',          'Unidade Popular',                  'ESQUERDA', 'extrema-esquerda'),
(90, 'PROS',        'Partido Republicano da Ordem Social', 'DIREITA', '');

/* Siglas historicas/renomeacoes para quando nr_partido vier nulo no candidato */
CREATE OR REPLACE TABLE dim_sigla_alias (
    sg_partido VARCHAR PRIMARY KEY,
    nr_partido INTEGER
);
INSERT INTO dim_sigla_alias (sg_partido, nr_partido) VALUES
('REPUBLICANOS', 10), ('PRB', 10),
('PL', 22), ('PR', 22),
('SOLIDARIEDADE', 77), ('SD', 77),
('UNIAO', 44), ('DEM', 25), ('PSL', 17), ('PRP', 44),
('PRD', 25), ('PODEMOS', 19), ('PODE', 19), ('PTN', 19), ('PSC', 20),
('PPS', 23), ('PMDB', 15), ('PMN', 33), ('MOBILIZA', 33),
('AVANTE', 70), ('PT do B', 70), ('PTdoB', 70),
('PTC', 36), ('PSDC', 27), ('UP', 80), ('PATRIOTA', 51);

/* Enriquece dim_partido existente (mantem compat com cargas) */
ALTER TABLE dim_partido ADD COLUMN IF NOT EXISTS nm_partido VARCHAR;
ALTER TABLE dim_partido ADD COLUMN IF NOT EXISTS campo VARCHAR;
ALTER TABLE dim_partido ADD COLUMN IF NOT EXISTS fonte VARCHAR;
UPDATE dim_partido d
   SET nm_partido = c.nm_partido, campo = c.campo, fonte = 'manual_campo_politico_2026'
  FROM dim_campo_partido c
 WHERE c.nr_partido = d.nr_partido;

/* View: candidato + campo politico (herdado do partido).
   Dedup: dim_candidato contem linhas duplicadas identicas para alguns
   candidatos (ex.: Haddad e Tarcisio em 2022) -> manter 1 registro por
   (ano_eletivo, sq_candidato), preferindo situacao 'APTO'. */
CREATE OR REPLACE VIEW vw_candidato_campo AS
WITH cam AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY ano_eletivo, sq_candidato
               ORDER BY (ds_situacao_candidatura = 'APTO') DESC,
                        ds_situacao_candidatura, nm_candidato
           ) AS rn
      FROM dim_candidato
), cam2 AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY ano_eletivo, nr_candidato,
                            UPPER(ds_cargo), sg_uf, sg_ue
               ORDER BY (ds_situacao_candidatura = 'APTO') DESC,
                        ds_situacao_candidatura
           ) AS rn2
      FROM cam
     WHERE rn = 1
)
SELECT c.ano_eletivo, c.sq_candidato, c.nr_candidato,
       c.nm_urna_candidato, COALESCE(NULLIF(TRIM(c.nm_urna_candidato), ''), c.nm_candidato) AS nm_candidato,
       c.sg_partido, COALESCE(c.nr_partido, a.nr_partido) AS nr_partido,
       p.sg_partido AS sg_canonica, p.nm_partido, p.campo, p.nota,
       c.cd_cargo, c.ds_cargo, c.sg_uf, c.sg_ue, c.nm_ue, c.ds_situacao_candidatura
  FROM cam2 c
  LEFT JOIN dim_sigla_alias a ON a.sg_partido = TRIM(c.sg_partido)
  LEFT JOIN dim_campo_partido p ON p.nr_partido = COALESCE(c.nr_partido, a.nr_partido)
 WHERE c.rn2 = 1;