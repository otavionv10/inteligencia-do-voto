#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_campo_zona_secao_brasil.py
FUNCAO    : Campo politico (ESQ/CEN/DIR) por ZONA e por SECAO, no banco BRASIL,
            para TODOS os cargos e anos presentes no fact_votacao_secao.
            Mesma logica do gerar_campo_municipio_brasil.py (vw_candidato_campo
            c1/c2 + dim_campo_partido p), agora nos niveis zona e secao.
            Fatiado por UF (loop) para controlar memoria. 1 registro por turno;
            shares sobre validos (95/96/97 excluidos).
DEPENDE   : data/db/brasil.duckdb (vw_candidato_campo, dim_campo_partido,
            dim_municipio).
SAIDAS    : data/analise/campo_brasil_por_zona.csv
            data/analise/campo_brasil_por_secao.csv
USO       : python _scripts/gerar_campo_zona_secao_brasil.py [--uf SP MG] [--nivel all|zona|secao]
Criado    : 2026-09-28
=============================================================================
"""
import argparse
import csv
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "analise"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def campo_join():
    return """
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


def sql_nivel(nivel, uf):
    """nivel: 'zona' ou 'secao'. Retorna SQL que agrega por UF."""
    group_cols = ["v.nr_turno", "v.cd_municipio_tse"]
    if nivel == "zona":
        group_cols += ["v.nr_zona"]
    else:
        group_cols += ["v.nr_zona", "v.nr_secao"]
    g = ", ".join(group_cols)
    return f"""
    WITH base AS (
        SELECT v.ano_eletivo,
               COALESCE(m.sg_uf, 'ZZ') AS sg_uf,
               upper(v.ds_cargo) AS cargo,
               v.nr_turno, v.cd_municipio_tse,
               v.nr_zona, v.nr_secao,
               v.qt_votos,
               COALESCE(c1.campo, c2.campo, p.campo) AS campo
        FROM fact_votacao_secao v
        LEFT JOIN dim_municipio m USING (cd_municipio_tse)
        {campo_join()}
        WHERE v.nr_votavel NOT IN (95, 96, 97)
          AND m.sg_uf = '{uf}'
    )
    SELECT sg_uf, ano_eletivo, lower(cargo) AS cargo,
           {g},
           COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'ESQUERDA'), 0) AS vot_esq,
           COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'CENTRO'),   0) AS vot_cen,
           COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'DIREITA'),  0) AS vot_dir,
           COALESCE(SUM(qt_votos) FILTER (WHERE campo IS NULL),     0) AS vot_sem_campo,
           SUM(qt_votos) AS validos
    FROM (SELECT * FROM base) v
    GROUP BY sg_uf, ano_eletivo, cargo, {g}
    ORDER BY sg_uf, ano_eletivo, cargo, nr_turno, cd_municipio_tse
    """


def append_csv(path, rows, nivel):
    exists = path.exists() and path.stat().st_size > 0
    with open(path, "a" if exists else "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if not exists:
            base = ["sg_uf", "ano_eletivo", "cargo", "nr_turno", "cd_municipio_tse"]
            if nivel == "zona":
                base += ["nr_zona"]
            else:
                base += ["nr_zona", "nr_secao"]
            w.writerow(base + ["vot_esq", "vot_cen", "vot_dir", "vot_sem_campo",
                               "validos", "share_esq", "share_cen", "share_dir",
                               "vencedor_campo"])
        for r in rows:
            uf, ano, carg, *gcols, esq, cen, dir_, sem, validos = r
            share = lambda x: (x / validos * 100) if validos else 0.0
            vencedor = ("DIREITA" if dir_ > esq and dir_ > cen
                        else "ESQUERDA" if esq > dir_ and esq > cen
                        else "CENTRO" if cen > dir_ and cen > esq
                        else "EMPATE") if validos else ""
            w.writerow([uf, ano, carg, *gcols, esq, cen, dir_, sem, validos,
                        round(share(esq), 2), round(share(cen), 2),
                        round(share(dir_), 2), vencedor])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", nargs="+", action="append", dest="ufs",
                    help="filtra por UF (padrao: todas com votacao)")
    ap.add_argument("--nivel", default="all", choices=["all", "zona", "secao"])
    ap.add_argument("--force", action="store_true",
                    help="sobrescreve CSVs existentes sem perguntar")
    ap.add_argument("--resume", action="store_true",
                    help="nao apaga CSV existente; so faz append das UFs pedidas")
    args = ap.parse_args()

    if args.ufs:
        ufs = sorted({u.upper() for grp in args.ufs for u in grp})
        if "BR" in ufs:
            print("BR nao e UF p/ zona/secao; ignorado.")
    else:
        ufs = None

    con = duckdb.connect(str(DB), read_only=True)
    if ufs is None:
        ufs = [r[0] for r in con.execute(
            "SELECT DISTINCT sg_uf FROM dim_municipio ORDER BY 1").fetchall()]
    print(f"UFs: {len(ufs)} -> {', '.join(ufs)}")

    niveis = ["zona", "secao"] if args.nivel == "all" else [args.nivel]
    for nivel in niveis:
        out = OUT_DIR / f"campo_brasil_por_{nivel}.csv"
        if out.exists() and not args.resume:
            if args.force or input(
                    f"{out.name} ja existe. Apagar e regerar? [s/N] "
            ).strip().lower() == "s":
                out.unlink()
            else:
                print(f"  skipp. usar --nivel {nivel} com o arquivo removido antes.")
                continue
        total = 0
        for uf in ufs:
            rows = con.execute(sql_nivel(nivel, uf)).fetchall()
            append_csv(out, rows, nivel)
            total += len(rows)
            print(f"  {uf}: {len(rows):>9,} linhas ({nivel}) | acumulado {total:,}")
        print(f"OK {out.name}: {total:,} linhas")

    con.close()
    print("fim.")


if __name__ == "__main__":
    sys.exit(main())