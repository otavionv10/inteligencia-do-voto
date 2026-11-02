#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/build_camada.py
FUNCAO    : Materializa a camada analitica (fact_voto_camada + agregados)
            FATIANDO o trabalho em blocos (ano, cargo) e (ano, cargo, zona%10)
            para reportar progresso em % a cada ~1% (Progress de progress.py).
            Idempotente: apaga por bloco antes de inserir.
DEPENDE   : _scripts/progress.py, DuckDB
USO       :
    python _scripts/build_camada.py                 # tudo
    python _scripts/build_camada.py --anos 2022     # so 2022 (smoke test)
    python _scripts/build_camada.py --agg off       # so fact_voto_camada
REGRA:
    As tabelas resultantes sao as MESMAS de 02_agregados.sql (equivalencia
    por UNION de blocos disjuntos; agregacoes sao SOMA -> fatiar e seguro).
=============================================================================
"""
import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from progress import Progress  # noqa: E402

DB = Path(r"D:\Dados_TSE\data\db\sao_paulo.duckdb")


# ---------------------------------------------------------------------------
# 1. fact_voto_camada (a pesada: 90M linhas com joins de candidato)
# ---------------------------------------------------------------------------
def build_fact_voto_camada(con, cafe, total, ProgressCls=Progress):
    con.execute("""
      CREATE OR REPLACE TABLE dim_candidato_map AS
      SELECT ano_eletivo, sq_candidato, nr_candidato, nm_candidato, sg_partido,
             nr_partido, nm_partido, campo, nota, cd_cargo,
             UPPER(ds_cargo) AS ds_cargo, sg_uf, sg_ue, nm_ue
        FROM vw_candidato_campo""")
    con.execute("""
      CREATE OR REPLACE TABLE dim_candidato_map_nr AS
      SELECT ano_eletivo, nr_candidato, ds_cargo, grupo,
             MIN(nm_candidato) nm_candidato, MIN(sg_partido) sg_partido,
             MIN(nm_partido) nm_partido, MIN(campo) campo
        FROM (SELECT ano_eletivo, nr_candidato, ds_cargo,
                     CASE WHEN ds_cargo IN ('PREFEITO','VICE-PREFEITO','VEREADOR')
                          THEN CAST(sg_ue AS VARCHAR) ELSE sg_uf END AS grupo,
                     nm_candidato, sg_partido, nm_partido, campo
                FROM dim_candidato_map)
       GROUP BY 1,2,3,4""")
    print("mapas prontos (dim_candidato_map / _nr)", flush=True)

    con.execute("DROP TABLE IF EXISTS fact_voto_camada")
    con.execute("""
      CREATE TABLE fact_voto_camada AS
      SELECT ano_eletivo, nr_turno, UPPER(ds_cargo) cargo,
             cd_municipio_tse, nr_zona, nr_secao, nr_local_votacao,
             nr_votavel, nm_votavel, qt_votos,
             CAST(NULL AS VARCHAR) nm_candidato, CAST(NULL AS VARCHAR) sg_partido,
             CAST(NULL AS VARCHAR) nm_partido, CAST(NULL AS VARCHAR) campo,
             CAST(NULL AS VARCHAR) tipo_voto
        FROM fact_votacao_secao WHERE 0""")

    # contagem por bloco p/ calibrar o progresso (cafe vem de main())
    todos = sorted({r[0] for r in cafe})
    okcols = "ano_eletivo,nr_turno,cd_municipio_tse,nr_zona,nr_secao,nr_local_votacao,nr_votavel,nm_votavel,qt_votos"

    inserts = [
        # sq_candidato presente -> join mapa por sq (1 registro/ano/sq)
        ("""INSERT INTO fact_voto_camada
            SELECT v.ano_eletivo, v.nr_turno, UPPER(v.ds_cargo), v.cd_municipio_tse,
                   v.nr_zona, v.nr_secao, v.nr_local_votacao, v.nr_votavel, v.nm_votavel,
                   v.qt_votos, k.nm_candidato, k.sg_partido, k.nm_partido, k.campo, 'NOMINAL'
              FROM s_camada v JOIN dim_candidato_map k
                ON k.ano_eletivo = v.ano_eletivo AND k.sq_candidato = v.sq_candidato
             WHERE MOD(v.nr_zona, 10) = %d AND v.sq_candidato IS NOT NULL"""),
        # sem sq_candidato (ou sq sentinela sem match) -> join mapa por nr+cargo+grupo
        ("""INSERT INTO fact_voto_camada
            SELECT v.ano_eletivo, v.nr_turno, UPPER(v.ds_cargo), v.cd_municipio_tse,
                   v.nr_zona, v.nr_secao, v.nr_local_votacao, v.nr_votavel, v.nm_votavel,
                   v.qt_votos, k.nm_candidato, k.sg_partido, k.nm_partido, k.campo, 'NOMINAL'
              FROM s_camada v JOIN dim_candidato_map_nr k
                ON k.ano_eletivo = v.ano_eletivo AND k.nr_candidato = v.nr_votavel
               AND k.ds_cargo = UPPER(v.ds_cargo)
               AND k.grupo = CASE WHEN UPPER(v.ds_cargo) IN ('PREFEITO','VICE-PREFEITO','VEREADOR')
                                  THEN v.cd_municipio_tse ELSE 'SP' END
             WHERE MOD(v.nr_zona, 10) = %d
               AND NOT EXISTS (SELECT 1 FROM dim_candidato_map m
                                WHERE m.ano_eletivo = v.ano_eletivo
                                  AND m.sq_candidato = v.sq_candidato)"""),
        # resto (branco/nulo/legenda/descartes) - anti-join por NOT EXISTS
        # (dim_candidato_map_nr cobre todos os candidatos -> 1 hash anti-join)
        ("""INSERT INTO fact_voto_camada
            SELECT v.ano_eletivo, v.nr_turno, UPPER(v.ds_cargo), v.cd_municipio_tse,
                   v.nr_zona, v.nr_secao, v.nr_local_votacao, v.nr_votavel, v.nm_votavel,
                   v.qt_votos,
                   CASE WHEN v.nr_votavel IN (95,96) THEN NULL ELSE v.nm_votavel END,
                   p2.sg_partido, p2.nm_partido, p2.campo,
                   CASE WHEN v.nr_votavel IN (95,96) THEN 'BRANCO_NULO'
                        WHEN p2.nr_partido IS NOT NULL THEN 'LEGENDA' ELSE 'DESCARTE' END
              FROM s_camada v LEFT JOIN dim_partido p2 ON p2.nr_partido = v.nr_votavel
             WHERE MOD(v.nr_zona, 10) = %d
               AND NOT EXISTS (SELECT 1 FROM dim_candidato_map_nr km
                                WHERE km.ano_eletivo = v.ano_eletivo
                                  AND km.nr_candidato = v.nr_votavel
                                  AND km.ds_cargo = UPPER(v.ds_cargo)
                                  AND km.grupo = CASE
                                      WHEN UPPER(v.ds_cargo) IN ('PREFEITO','VICE-PREFEITO','VEREADOR')
                                      THEN v.cd_municipio_tse ELSE 'SP' END)"""),
    ]

    ano_cargos = sorted({(r[0], r[1]) for r in cafe})
    with ProgressCls(total, label="fact_voto_camada", every_pct=1.0) as p:
        for ano, cargo in ano_cargos:
            # 1 scan da fact por (ano,cargo) -> temp table em memoria/disco
            p.message(f"materializando {ano} {cargo}")
            con.execute("DROP TABLE IF EXISTS s_camada")
            con.execute(
                "CREATE TEMP TABLE s_camada AS "
                "SELECT * FROM fact_votacao_secao "
                "WHERE ano_eletivo = ? AND UPPER(ds_cargo) = ?",
                [ano, cargo])
            con.execute("CREATE INDEX IF NOT EXISTS ix_sc_sq ON s_camada(sq_candidato)")
            con.execute("CREATE INDEX IF NOT EXISTS ix_sc_nr ON s_camada(nr_votavel)")
            for m in range(10):
                n_bloco = next((r[3] for r in cafe
                                if r[0] == ano and r[1] == cargo and r[2] == m), 0)
                for q in inserts:
                    con.execute(q % (m,))
                p.tick(n_bloco)
                p.message(f"ano {ano} | {cargo} | zona%10={m}")
        con.execute("DROP TABLE IF EXISTS s_camada")
    print(f"\nfact_voto_camada: {con.execute('SELECT count(*) FROM fact_voto_camada').fetchone()[0]:,} linhas")


# ---------------------------------------------------------------------------
# 2. agregados (SOMA em cada fatia = mesmo resultado canônico de 02_agregados)
# ---------------------------------------------------------------------------
def build_aggs(con, cafe, total, ProgressCls=Progress):
    # cafe: [(ano, cargo, zona_mod, n_linhas)]
    aggs = [
        # nome, fonte, grupo, colunas de soma extracol
        ("agg_municipio_totais", "fact_votacao_secao",
         "ano_eletivo, cargo, cd_municipio_tse",
         """SELECT ano_eletivo, cargo, cd_municipio_tse,
                   SUM(ap) aptos, SUM(cm) comparecimento, SUM(ab) abstencoes
              FROM (SELECT ano_eletivo, UPPER(ds_cargo) cargo, cd_municipio_tse,
                           nr_zona, nr_secao,
                           MAX(qt_aptos) ap, MAX(qt_comparecimento) cm,
                           MAX(qt_abstencoes) ab
                      FROM fact_votacao_secao
                     WHERE {slice}
                     GROUP BY 1,2,3,4,5) s
             GROUP BY 1,2,3"""),
        ("agg_zona_totais", "fact_votacao_secao",
         "ano_eletivo, cargo, cd_municipio_tse, nr_zona",
         """SELECT ano_eletivo, cargo, cd_municipio_tse, nr_zona,
                   SUM(ap) aptos, SUM(cm) comparecimento, SUM(ab) abstencoes
              FROM (SELECT ano_eletivo, UPPER(ds_cargo) cargo, cd_municipio_tse,
                           nr_zona, nr_secao,
                           MAX(qt_aptos) ap, MAX(qt_comparecimento) cm,
                           MAX(qt_abstencoes) ab
                      FROM fact_votacao_secao
                     WHERE {slice}
                     GROUP BY 1,2,3,4,5) s
             GROUP BY 1,2,3,4"""),
        ("agg_voto_municipio_partido", "fact_voto_camada",
         "ano_eletivo, nr_turno, cargo, cd_municipio_tse, sg_partido, nm_partido, campo",
         """SELECT t.ano_eletivo, t.nr_turno, t.cargo, t.cd_municipio_tse,
                   t.sg_partido, t.nm_partido, t.campo, t.votos, v.validos
              FROM (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
                           sg_partido, nm_partido, campo, SUM(qt_votos) votos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4,5,6,7) t
              JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
                           SUM(qt_votos) validos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4) v
                USING (ano_eletivo, nr_turno, cargo, cd_municipio_tse)"""),
        ("agg_voto_zona_partido", "fact_voto_camada",
         "ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona, sg_partido, nm_partido, campo",
         """SELECT t.ano_eletivo, t.nr_turno, t.cargo, t.cd_municipio_tse, t.nr_zona,
                   t.sg_partido, t.nm_partido, t.campo, t.votos, v.validos
              FROM (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
                           sg_partido, nm_partido, campo, SUM(qt_votos) votos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4,5,6,7,8) t
              JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
                           SUM(qt_votos) validos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4,5) v
                USING (ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona)"""),
        ("agg_voto_municipio_candidato", "fact_voto_camada",
         "ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_candidato, nm_candidato, sg_partido, nm_partido, campo",
         """SELECT t.ano_eletivo, t.nr_turno, t.cargo, t.cd_municipio_tse,
                   t.nr_candidato, t.nm_candidato, t.sg_partido, t.nm_partido,
                   t.campo, t.votos, v.validos
              FROM (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
                           nr_votavel nr_candidato, nm_candidato, sg_partido,
                           nm_partido, campo, SUM(qt_votos) votos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto = 'NOMINAL'
                     GROUP BY 1,2,3,4,5,6,7,8,9) t
              JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
                           SUM(qt_votos) validos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4) v
                USING (ano_eletivo, nr_turno, cargo, cd_municipio_tse)"""),
        ("agg_voto_zona_candidato", "fact_voto_camada",
         "ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona, nr_candidato, nm_candidato, sg_partido, nm_partido, campo",
         """SELECT t.ano_eletivo, t.nr_turno, t.cargo, t.cd_municipio_tse, t.nr_zona,
                   t.nr_candidato, t.nm_candidato, t.sg_partido, t.nm_partido,
                   t.campo, t.votos, v.validos
              FROM (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
                           nr_votavel nr_candidato, nm_candidato, sg_partido,
                           nm_partido, campo, SUM(qt_votos) votos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto = 'NOMINAL'
                     GROUP BY 1,2,3,4,5,6,7,8,9,10) t
              JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
                           SUM(qt_votos) validos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4,5) v
                USING (ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona)"""),
        ("agg_voto_local_partido", "fact_voto_camada",
         "ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_local_votacao, sg_partido, nm_partido, campo",
         """SELECT t.ano_eletivo, t.nr_turno, t.cargo, t.cd_municipio_tse,
                   t.nr_local_votacao, t.sg_partido, t.nm_partido, t.campo,
                   t.votos, v.validos
              FROM (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
                           nr_local_votacao, sg_partido, nm_partido, campo,
                           SUM(qt_votos) votos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4,5,6,7,8) t
              JOIN (SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
                           nr_local_votacao, SUM(qt_votos) validos
                      FROM fact_voto_camada
                     WHERE {slice} AND tipo_voto IN ('NOMINAL','LEGENDA')
                     GROUP BY 1,2,3,4,5) v
                USING (ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_local_votacao)"""),
    ]

    ano_cargos = sorted({(r[0], r[1]) for r in cafe})
    with ProgressCls(total, label="agregados", every_pct=1.0) as prog:
        for nome, fonte, _grupo, sql_tpl in aggs:
            con.execute(f"DROP TABLE IF EXISTS {nome}")
            con.execute(f"CREATE TABLE {nome} AS SELECT * FROM ({sql_tpl.format(slice='0=1')}) LIMIT 0")
            for ano, cargo in ano_cargos:
                if fonte == "fact_votacao_secao":
                    sl = (f"ano_eletivo = {ano} AND UPPER(ds_cargo) = '{cargo}'")
                else:
                    sl = (f"ano_eletivo = {ano} AND cargo = '{cargo}'")
                con.execute(sql_tpl.format(slice=sl) and
                            f"INSERT INTO {nome} " + sql_tpl.format(slice=sl))
            prog.tick(total / len(aggs))
            n = con.execute(f"SELECT count(*) FROM {nome}").fetchone()[0]
            print(f"\n{nome}: {n:,}", flush=True)

    # views (idênticas às do 02_agregados.sql)
    con.execute(VIEWS_SQL)
    print("\nviews recriadas")


VIEWS_SQL = """
CREATE OR REPLACE VIEW vw_voto_municipio_partido AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
       sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_municipio_partido;

CREATE OR REPLACE VIEW vw_voto_zona_partido AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
       sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_zona_partido;

CREATE OR REPLACE VIEW vw_voto_local_partido AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_local_votacao,
       sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_local_partido;

CREATE OR REPLACE VIEW vw_voto_municipio_candidato AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse,
       nr_candidato, nm_candidato, sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_municipio_candidato;

CREATE OR REPLACE VIEW vw_voto_zona_candidato AS
SELECT ano_eletivo, nr_turno, cargo, cd_municipio_tse, nr_zona,
       nr_candidato, nm_candidato, sg_partido, nm_partido, campo, votos, validos,
       ROUND(100.0 * votos / NULLIF(validos, 0), 2) AS share_validos_pct
  FROM agg_voto_zona_candidato;
"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", help="anos separados por virgula (default: todos)")
    ap.add_argument("--agg", default="on", choices=["on", "off"], help="constroi agregados")
    args = ap.parse_args()

    con = duckdb.connect(str(DB))
    con.execute("PRAGMA threads=8")

    anos = [int(a) for a in args.anos.split(",")] if args.anos else None
    filtra = (" WHERE ano_eletivo IN (" + ",".join(str(a) for a in anos) + ")") if anos else ""
    cafe = con.execute(f"""
        SELECT ano_eletivo, UPPER(ds_cargo) cargo, MOD(nr_zona,10) m, count(*)
          FROM fact_votacao_secao{filtra}
         GROUP BY 1,2,3 ORDER BY 1,2,3""").fetchall()
    total = sum(r[3] for r in cafe)
    print(f"fatias: {len(cafe)} | linhas a processar: {total:,}", flush=True)

    build_fact_voto_camada(con, cafe, total, Progress)
    if args.agg == "on":
        build_aggs(con, cafe, total, Progress)
    con.close()


if __name__ == "__main__":
    main()