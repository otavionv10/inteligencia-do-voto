# LOGICA DO BANCO - Dados TSE Sao Paulo

## Regras de negocio ativas

### Identificadores
- `cd_municipio_tse` e VARCHAR(5) SEMPRE com zero-padding (ex.: "61018").
  Nunca converter para INTEGER (perde o zero inicial).
- `nr_zona` e `nr_secao` sao INTEGER.
- `nr_votavel` e INTEGER; valores especiais: 95=BRANCOS, 96=NULOS, 97=LEGENDA, 0=NOMINAL.
- `qt_*` (aptos, comparecimento, votos) sao BIGINT.

### Coordenadas geograficas
- Latitude/longitude no TSE usam **virgula decimal** ("-23,5549967").
- Converter para DOUBLE com ponto decimal (replace ',' -> '.').

### Encoding
- Todos os CSVs do TSE: **Latin-1**, delimitador `;`, todos os campos entre aspas duplas.

### Totais por secao (aptos / comparecimento / abstencao)
- **NAO existem** `QT_APTOS/QT_COMPARECIMENTO` nas `votacao_secao` (2014-2024) —
  a fact_votacao_secao so tem votos por votavel/secacao. Quantidades de eleitores
  aptos por secao so existem para 2022/2024/2026 (via `fact_eleitorado_local`).
- Comparecimento calculado = soma de `qt_votos` de UM cargo por secao
  (nominais + legenda + brancos + nulos = 1 voto por eleitor).
- Abstencao = aptos(secao) - comparecimento(calculado).

### Cargos
- Nome do cargo vem inconsistente em caixa entre anos: 2016 usa 'PREFEITO'/'VEREADOR'
  em caixa alta; 2020/2024 usam 'Prefeito'/'Vereador'; anos gerais 'Governador' etc.
  Normalizar com `UPPER(ds_cargo)` nas queries.
- Nas anuais, nao vem 'Presidente': arquivo estadual so tem Governador/Senador/
  Dep.Federal/Dep.Estadual.

### Seções
- Secoes agregadas: `cd_tipo_secao_agregada = 1` e `nr_secao_principal = -1` em alguns anos.
- Tratamento temporal: cada ano e um snapshot proprio (dim_secao por ano_eletivo).

## Filtros padrao
- Estado: `sg_uf = 'SP'` na origem; os arquivos de perfil/votacao ja sao SP.
- Candidaturas: carregados do arquivo `_SP.csv` de cada ano; dim_candidato ja vem
  filtrado para SP (`sg_uf='SP'`), recebe um registro por turno/registro (sem PK unica).

## Fontes e datas disponiveis
- Eleitorado por secao: 2020, 2022, 2024, 2026
- Votacao por secao: 2014, 2016, 2018, 2020, 2022, 2024
- Local de votacao: 2022, 2024, 2026
- Candidaturas: 2016-2024
- Mapa TSE-IBGE: snapshot 2026-09-20
- Enriquecimento IBGE (dim_municipio, geocodigo IBGE 7 digitos):
  * censo 2022: ibge_pop_2022, ibge_area_km2, ibge_dens_2022 (hab/km2)
  * pib 2023: ibge_pib_2023_mil (R$ mil), ibge_pib_pc_2023 (R$; PIB*1000/pop censo 2022)
  * idhm 2010 (Atlas PNUD): ibge_idhm_2010 + educacao/longevidade/renda (0..1)
  Fonte: SIDRA tabelas 4714 e 5938 + shapefile SEADE (2010) — script _scripts/enrich_ibge.py

## Historico de alteracoes de schema
- 2026-09-20 - criacao do schema (v001). Colunas finais dos anos antigos pendentes de inspecao.
- 2026-09-20 - v002 (banco carregado): inspecao completa dos headers; ajustes:
  * fact_votacao_secao: sem colunas QT_* de total (NULL);
    adicionados cd_tipo_eleicao, nm_eleicao, dt_eleicao, nm_local_votacao, sq_candidato;
  * fact_eleitorado_perfil: tp_obrigatoriedade_voto VARNCHAR (texto 'Obrigatório'/'Facultativo');
    adicionadas colunas de estado civil, identidade de genero, quilombola, libras, nome social;
  * dim_local_votacao: PK composta (ano, municipio, local) - local atende varias zonas;
  * dim_candidato: sem PK unica (registros repetem por turno); adicionado sg_uf.