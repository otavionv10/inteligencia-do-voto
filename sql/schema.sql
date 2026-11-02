/*
=============================================================================
QUERY     : schema.sql
BANCO     : sao_paulo.duckdb (DuckDB 1.5+)
FUNCAO    : Cria o star schema do projeto (municipio -> zona -> local -> secao)
FONTES    : municipio_tse_ibge, eleitorado_local_votacao, perfil_eleitor_secao,
            votacao_secao, consulta_cand
CRIADO    : 2026-09-20
ALTERADO  : 2026-09-20 - criacao (rascunho; colunas finais apos inspecao real)
=============================================================================
*/

/* ---------- DIMENSAO GEOGRAFICA ---------- */

CREATE TABLE IF NOT EXISTS dim_municipio (
    cd_municipio_tse  VARCHAR(5) PRIMARY KEY,
    nm_municipio_tse  VARCHAR NOT NULL,
    cd_municipio_ibge VARCHAR(7),
    sg_uf             VARCHAR(2) NOT NULL,
    nm_uf             VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_secao (
    ano_eletivo             INTEGER NOT NULL,
    cd_municipio_tse        VARCHAR(5) NOT NULL,
    nr_zona                 INTEGER NOT NULL,
    nr_secao                INTEGER NOT NULL,
    cd_tipo_secao_agregada  INTEGER,
    ds_tipo_secao_agregada  VARCHAR,
    nr_secao_principal      INTEGER,
    cd_situ_secao           INTEGER,
    ds_situ_secao           VARCHAR,
    cd_situ_acessibilidade  INTEGER,
    ds_situ_acessibilidade  VARCHAR,
    PRIMARY KEY (ano_eletivo, cd_municipio_tse, nr_zona, nr_secao)
);

CREATE TABLE IF NOT EXISTS dim_local_votacao (
    ano_eletivo        INTEGER NOT NULL,
    cd_municipio_tse   VARCHAR(5) NOT NULL,
    nr_zona            INTEGER NOT NULL,
    nr_local_votacao   INTEGER NOT NULL,
    nm_local_votacao   VARCHAR,
    ds_tipo_local      VARCHAR,
    ds_endereco        VARCHAR,
    nm_bairro          VARCHAR,
    nr_cep             VARCHAR,
    nr_latitude        DOUBLE,
    nr_longitude       DOUBLE,
    cd_situ_local      INTEGER,
    ds_situ_local      VARCHAR,
    PRIMARY KEY (ano_eletivo, cd_municipio_tse, nr_zona, nr_local_votacao)
);
-- ADR-008 (2026-09-26): nr_zona adicionado a chave. O numero do local de votacao se
-- repete entre zonas de um mesmo municipio; sem nr_zona, dim_local_votacao colapsava
-- locais distintos (SP 2022: 10.845 reais -> 7.483 colapsados). Mesmo fix ja aplicado
-- no banco BR (load_brasil.py). Migracao da tabela existente feita em load.py (main()).

/* ---------- DIMENSAO POLITICA ---------- */

CREATE TABLE IF NOT EXISTS dim_partido (
    nr_partido INTEGER PRIMARY KEY,
    sg_partido  VARCHAR,
    nm_partido  VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_candidato (
    ano_eletivo            INTEGER NOT NULL,
    sq_candidato           BIGINT NOT NULL,
    nr_candidato           INTEGER,
    nm_candidato           VARCHAR,
    nm_urna_candidato      VARCHAR,
    sg_partido             VARCHAR,
    nr_partido             INTEGER,
    cd_cargo               INTEGER,
    ds_cargo               VARCHAR,
    cd_situacao_candidatura INTEGER,
    ds_situacao_candidatura VARCHAR,
    cd_situacao_turno      INTEGER,
    ds_situacao_turno      VARCHAR,
    sg_uf                  VARCHAR,
    cd_genero              INTEGER,
    ds_genero              VARCHAR,
    cd_grau_instrucao      INTEGER,
    ds_grau_instrucao      VARCHAR,
    cd_estado_civil        INTEGER,
    ds_estado_civil        VARCHAR,
    cd_cor_raca            INTEGER,
    ds_cor_raca            VARCHAR,
    ds_ocupacao            VARCHAR,
    sg_ue                  VARCHAR,
    nm_ue                  VARCHAR
);
CREATE INDEX IF NOT EXISTS idx_dim_candidato_sq
    ON dim_candidato (ano_eletivo, sq_candidato);

/* ---------- FATOS ---------- */

CREATE TABLE IF NOT EXISTS fact_eleitorado_local (
    ano_eletivo       INTEGER NOT NULL,
    nr_turno          INTEGER,
    cd_municipio_tse  VARCHAR(5) NOT NULL,
    nr_zona           INTEGER NOT NULL,
    nr_secao          INTEGER NOT NULL,
    nr_local_votacao  INTEGER,
    qt_eleitor_secao  BIGINT,
    qt_eleit_federal  BIGINT,
    qt_eleit_estadual BIGINT,
    qt_eleit_municipal BIGINT
);

CREATE TABLE IF NOT EXISTS fact_eleitorado_perfil (
    ano_eletivo          INTEGER NOT NULL,
    cd_eleicao           INTEGER,
    cd_municipio_tse     VARCHAR(5) NOT NULL,
    nr_zona              INTEGER NOT NULL,
    nr_secao             INTEGER NOT NULL,
    nr_local_votacao     INTEGER,
    ds_genero            VARCHAR,
    ds_estado_civil      VARCHAR,
    ds_grau_escolaridade VARCHAR,
    ds_faixa_etaria      VARCHAR,
    ds_cor_raca          VARCHAR,
    cd_identidade_genero INTEGER,
    ds_identidade_genero VARCHAR,
    cd_quilombola        INTEGER,
    ds_quilombola        VARCHAR,
    cd_interprete_libras INTEGER,
    ds_interprete_libras VARCHAR,
    tp_obrigatoriedade_voto VARCHAR,
    cd_genero            INTEGER,
    cd_estado_civil      INTEGER,
    cd_faixa_etaria      INTEGER,
    cd_grau_escolaridade INTEGER,
    cd_raca_cor          INTEGER,
    qt_eleitores_perfil  BIGINT,
    qt_eleitores_biometria BIGINT,
    qt_eleitores_deficiencia BIGINT,
    qt_eleitores_nome_social BIGINT
);

CREATE TABLE IF NOT EXISTS fact_votacao_secao (
    ano_eletivo      INTEGER NOT NULL,
    cd_tipo_eleicao  INTEGER,
    nm_tipo_eleicao  VARCHAR,
    cd_eleicao       INTEGER,
    nm_eleicao       VARCHAR,
    dt_eleicao       VARCHAR,
    nr_turno         INTEGER,
    cd_municipio_tse VARCHAR(5) NOT NULL,
    nr_zona          INTEGER NOT NULL,
    nr_secao         INTEGER NOT NULL,
    nr_local_votacao INTEGER,
    nm_local_votacao VARCHAR,
    cd_cargo         INTEGER,
    ds_cargo         VARCHAR,
    qt_aptos         BIGINT,
    qt_comparecimento BIGINT,
    qt_abstencoes    BIGINT,
    qt_votos_nominais BIGINT,
    qt_votos_brancos BIGINT,
    qt_votos_nulos   BIGINT,
    qt_votos_legenda BIGINT,
    nr_votavel       INTEGER,
    nm_votavel       VARCHAR,
    sg_partido       VARCHAR,
    sq_candidato     BIGINT,
    qt_votos         BIGINT
);

/* ---------- INDICES ---------- */

CREATE INDEX IF NOT EXISTS idx_secao_ano      ON dim_secao (ano_eletivo, cd_municipio_tse);
CREATE INDEX IF NOT EXISTS idx_fel_sec        ON fact_eleitorado_local (ano_eletivo, cd_municipio_tse, nr_zona, nr_secao);
CREATE INDEX IF NOT EXISTS idx_fep_sec        ON fact_eleitorado_perfil (ano_eletivo, cd_municipio_tse, nr_zona, nr_secao);
CREATE INDEX IF NOT EXISTS idx_fvs_sec        ON fact_votacao_secao (ano_eletivo, cd_municipio_tse, nr_zona, nr_secao);
CREATE INDEX IF NOT EXISTS idx_fvs_cargo      ON fact_votacao_secao (ano_eletivo, cd_cargo);
CREATE INDEX IF NOT EXISTS idx_fvs_votavel    ON fact_votacao_secao (ano_eletivo, nr_votavel);
CREATE INDEX IF NOT EXISTS idx_cand_ano       ON dim_candidato (ano_eletivo, sg_ue);
CREATE INDEX IF NOT EXISTS idx_local_ano_mun  ON dim_local_votacao (ano_eletivo, cd_municipio_tse);