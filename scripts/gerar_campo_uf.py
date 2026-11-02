# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_campo_uf.py
FUNCAO    : Campo politico (ESQ/CEN/DIR) por UF no banco BRASIL
            Presidente (2014/18/22) + Governador (2014/18/22) + Dep. Federal (2014/18/22)
            -> dim_municipio.sg_uf como base de UF (cd_municipio_tse NAO embute UF)
CSVs (UTF-8 BOM):
   data/analise/campo_brasil_por_cargo_uf.csv   - frame amplo (uf, ano, cargo, turno, campos)
   data/analise/ranking_uf_direita_{cargo}_{ano}_{turno}.csv  - sort %DIR (>=1000 validos)
REQUER    : data/db/brasil.duckdb (load_brasil.py) + camada_analitica (vw_candidato_campo)
USO       : python _scripts/gerar_campo_uf.py [--anos 2014 2018 2022]
CRIADO    : 2026-09-23
=============================================================================
"""
import argparse
import csv
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT = Path(__file__).resolve().parent.parent / "data" / "analise"
OUT.mkdir(parents=True, exist_ok=True)

ANOS = (2014, 2018, 2022)
CARGOS = ("PRESIDENTE", "GOVERNADOR", "DEPUTADO FEDERAL")


def campo_join():
    """SELECT fields: c1 por sq_candidato (2018/22), fallback c2 por nr (2014),
       e p por partido p/ votos de legenda (sq_candidato IS NULL, deputados)."""
    return f"""
    LEFT JOIN vw_candidato_campo c1
           ON c1.ano_eletivo = v.ano_eletivo AND c1.sq_candidato = v.sq_candidato
    LEFT JOIN vw_candidato_campo c2
           ON c2.ano_eletivo = v.ano_eletivo
          AND c2.nr_candidato = v.nr_votavel
          AND upper(c2.ds_cargo) = upper(v.ds_cargo)
          AND c2.sg_uf = CASE WHEN upper(v.ds_cargo) = 'PRESIDENTE'
                              THEN 'BR' ELSE COALESCE(m.sg_uf, '--') END
    LEFT JOIN dim_campo_partido p
           ON p.nr_partido = v.nr_votavel AND COALESCE(v.sq_candidato, -1) < 0
    """


def gen(anos):
    fila = []
    for ano in anos:
        for cargo in CARGOS:
            q = f"""
            WITH base AS (
                SELECT v.ano_eletivo,
                       m.sg_uf,
                       v.nr_turno,
                       upper(v.ds_cargo) AS cargo,
                       v.nr_votavel, v.qt_votos,
                       COALESCE(c1.campo, c2.campo, p.campo) AS campo
                FROM fact_votacao_secao v
                JOIN dim_municipio m USING (cd_municipio_tse)
                {campo_join()}
                WHERE v.ano_eletivo = {ano}
                  AND upper(v.ds_cargo) = '{cargo}'
                  AND v.nr_votavel NOT IN (95, 96, 97)
            )
            SELECT sg_uf, ano_eletivo, cargo, nr_turno,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'ESQUERDA'), 0) AS votos_esq,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'CENTRO'),   0) AS votos_cen,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'DIREITA'),  0) AS votos_dir,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo IS NULL),     0) AS votos_sem_campo,
                   SUM(qt_votos) AS votos_validos
            FROM base
            GROUP BY sg_uf, ano_eletivo, cargo, nr_turno
            ORDER BY sg_uf, nr_turno
            """
            fila.append((ano, cargo, q))
    return fila


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", nargs="+", type=int, default=list(ANOS))
    ap.add_argument("--cargos", nargs="+", default=list(CARGOS))
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    print(f"banco: {DB}  |  anos {args.anos}  |  cargos {args.cargos}")

    all_rows = []
    for ano in args.anos:
        for cargo in args.cargos:
            cargou = cargo.upper()
            if ano not in ANOS or cargou not in CARGOS:
                print(f"  skip {cargo} {ano}")
                continue
            print(f"  campo {cargou} {ano} ...")
            q = f"""
            WITH base AS (
                SELECT v.ano_eletivo, COALESCE(m.sg_uf, 'ZZ') AS sg_uf, v.nr_turno,
                       upper(v.ds_cargo) AS cargo,
                       v.qt_votos, COALESCE(c1.campo, c2.campo, p.campo) AS campo
                FROM fact_votacao_secao v
                LEFT JOIN dim_municipio m USING (cd_municipio_tse)
                {campo_join()}
                WHERE v.ano_eletivo = {ano}
                  AND upper(v.ds_cargo) = '{cargou}'
                  AND v.nr_votavel NOT IN (95, 96, 97)
            )
            SELECT sg_uf, ano_eletivo, lower(cargo) AS cargo, nr_turno,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'ESQUERDA'), 0) AS votos_esq,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'CENTRO'),   0) AS votos_cen,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'DIREITA'),  0) AS votos_dir,
                   COALESCE(SUM(qt_votos) FILTER (WHERE campo IS NULL),     0) AS votos_sem_campo,
                   SUM(qt_votos) AS votos_validos
            FROM base
            GROUP BY sg_uf, ano_eletivo, cargo, nr_turno
            ORDER BY sg_uf, nr_turno
            """
            rows = con.execute(q).fetchall()
            all_rows.extend(rows)

    # ---- CSV amplo
    csv_path = OUT / "campo_brasil_por_cargo_uf.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sg_uf", "ano_eletivo", "cargo", "nr_turno",
                    "votos_esq", "votos_cen", "votos_dir", "votos_sem_campo", "votos_validos",
                    "pct_esq", "pct_cen", "pct_dir"])
        nrow = 0
        for r in sorted(all_rows):
            uf, ano, carg, turno, esq, cen, dir_, sem, validos = r
            p = lambda x: (x / validos * 100) if validos else 0
            w.writerow([uf, ano, carg, turno, esq, cen, dir_, sem, validos,
                        round(p(esq), 3), round(p(cen), 3), round(p(dir_), 3)])
            nrow += 1
    print(f"  csv amplo: {csv_path} ({nrow} linhas)")

    # ---- rankings %DIR por UF (min 1000 validos)
    for ano in args.anos:
        for cargou in args.cargos:
            cargou = cargou.upper()
            if cargou not in CARGOS:
                continue
            turnos = con.execute("""
                SELECT DISTINCT nr_turno FROM fact_votacao_secao
                WHERE ano_eletivo=? AND upper(ds_cargo)=? ORDER BY 1""", [ano, cargou]).fetchall()
            for (turno,) in turnos:
                fr = [r for r in all_rows if r[1] == ano and r[2] == cargou.lower() and r[3] == turno]
                fr = [r for r in fr if r[8] >= 1000]
                fr.sort(key=lambda r: (r[6] / r[8] if r[8] else 0), reverse=True)
                if not fr:
                    continue
                fn = f"ranking_uf_direita_{cargou.lower().replace(' ', '_')}_{ano}_t{turno}.csv"
                with open(OUT / fn, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["sg_uf", "votos_dir", "votos_validos", "pct_dir", "pct_esq", "pct_cen"])
                    for r in fr:
                        uf, _, _, _, esq, cen, dir_, sem, validos = r
                        w.writerow([uf, dir_, validos,
                                    round(dir_ / validos * 100, 3),
                                    round(esq / validos * 100, 3),
                                    round(cen / validos * 100, 3)])
                print(f"  {fn}")

    con.close()
    print("OK")


if __name__ == "__main__":
    sys.exit(main())