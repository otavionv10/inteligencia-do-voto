# Inteligência do Voto

Ciência de dados eleitoral e geoespacial com dados públicos do **TSE** e do **IBGE**, em escala nacional.

**Pergunta:** onde, local de votação por local de votação, o eleitorado está consolidado, onde é persuasível e onde a abstenção é a maior oportunidade?

| Escala | |
|---|---|
| Banco analítico | DuckDB, cerca de 31 GB |
| Período | eleições de 2012 a 2024, todos os cargos |
| Cobertura | 27 UFs, 5.570 municípios |
| Seções eleitorais | cerca de 1,5 milhão |
| Locais de votação | 281.576 cadastrados |
| Campo político por seção | 12,6 milhões de linhas |

> Os dados brutos e o banco não estão no repositório (são públicos e pesados). Os scripts baixam tudo das fontes oficiais.

---

## Pipeline

```
TSE Dados Abertos ──► downloader.py ──► load.py / load_brasil.py ──► DuckDB
IBGE (Censo 2022, PIB, IDHM, setores) ──► enrich_ibge*.py ─────────────┘
                                                                         │
                                       sql/queries/q01…q26 ◄─────────────┘
                                                │
                     gerar_mapa_* / gerar_dashboard_* / gerar_ranking_*
                                                │
                              mapas HTML, dashboards e CSV/Excel
```

- **`scripts/downloader.py`**: download retomável com checksum. O servidor do TSE bloqueia clientes comuns, então o download usa `curl_cffi`.
- **`scripts/load.py`**: extrai e normaliza os arquivos. Os CSVs do TSE vêm em Latin-1 e separados por `;`, as coordenadas usam vírgula decimal e os nomes de colunas mudam entre eleições.
- **`sql/schema.sql`**: modelo do banco (dimensões de município, seção, local de votação e candidato; fatos de votação e eleitorado).
- **`sql/queries/`**: 26 consultas versionadas, cada uma com cabeçalho de objetivo, fontes e saída.

### Validação

Os totais são conferidos contra os números oficiais. Exemplo: o estado de São Paulo dentro da base Brasil bate exatamente com a base estadual (25.656.334 votos válidos no 2º turno de 2022).

---

## Análises

### Índice de prioridade de campanha (`q20`–`q22`, `q26`)

Cruza a **força do campo político** em cada local (participação nos votos válidos) com a **abstenção** (comparecimento sobre aptos) e classifica o local em quatro quadrantes:

| Quadrante | Regra | Leitura |
|---|---|---|
| Base consolidada | força ≥ 60% e abstenção baixa | manter |
| Mobilização | força ≥ 60% e abstenção alta | levar o eleitor às urnas |
| Disputa | margem próxima de 50% | persuasão, ponderada pelo eleitorado |
| Hostil | força ≤ 30% | baixo retorno por esforço |

### Voto dividido entre cargos (`q23`)

Compara o vencedor de presidente, governador e deputado federal no mesmo local. Um local que troca de lado conforme o cargo prova que aquele eleitorado é persuasível, o que é um sinal mais forte do que uma margem apertada isolada.

### Trajetória 2014 → 2018 → 2022 (`q24`)

Classifica cada local em 7 perfis de movimento (moveu forte à direita, moderado, estável, oscilou...) com regras interpretáveis baseadas na variação em pontos percentuais.

### Voto, abstenção e indicadores socioeconômicos (`q07`, `q10`–`q12`, `q25`)

Correlação entre resultado, abstenção, IDHM, PIB per capita e perfil do eleitorado.

---

## Ética e limites

- Só dados **públicos e agregados**. Não existe voto individual nos dados do TSE.
- **Local de votação não é residência.** Análises que atribuem o voto à vizinhança da escola são estimativas e aparecem sinalizadas.
- A classificação dos partidos em esquerda, centro e direita é uma **escolha metodológica**, documentada em `sql/camada_analitica/01_classificacao_partidos.sql`.
- Separação explícita entre fato apurado, inferência e cenário.

## Próximos passos

- Clusterização (k-means e agrupamento hierárquico) das trajetórias, comparada às regras atuais.
- Normalização por 1.000 eleitores aptos em todos os mapas.

## Como rodar

```bash
pip install -r requirements.txt
export TSE_DATA_DIR=/caminho/para/dados     # opcional; padrão: ./data
python scripts/downloader.py
python scripts/load.py
python scripts/enrich_ibge.py
```

Alguns scripts ainda têm caminhos locais fixos (`D:/...`) da máquina de desenvolvimento; ajuste-os ou use `TSE_DATA_DIR`.

## Stack

Python · DuckDB · SQL · Leaflet · TSE Dados Abertos · IBGE

---

Autor: **Otávio Augusto Camara Rabello** · [Portfólio de dados](https://hubdropshipping.com.br/portfolio/dados/) · [LinkedIn](https://www.linkedin.com/in/otavionv10/)
