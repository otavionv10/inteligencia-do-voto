#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_ranking_secao_estados.py
FUNCAO    : Ranking por ESTADO das secoes e zonas mais de DIREITA e de
            ESQUERDA (presidente T2 + deputado federal T1, 2014/18/22).
            Le os CSVs campo_brasil_por_{zona,secao}.csv (ja gerados) e grava
            por UF arquivos ordenados por % de share e por total.
METRICAS  : share = votos do campo / validos (95/96/97 excluidos).
            Ordenacao por % aplica piso de validos (PISO).
SAIDAS    : data/analise/ranking_estados/{UF}/
              ranking_{UF}_{nivel}_{cargo}_{ano}_t{t}_direita.csv      (% dir)
              ranking_{UF}_{nivel}_{cargo}_{ano}_t{t}_direita_abs.csv  (total)
              ranking_{UF}_{nivel}_{cargo}_{ano}_t{t}_esquerda.csv     (% esq)
              ranking_{UF}_{nivel}_{cargo}_{ano}_t{t}_esquerda_abs.csv
USO       : python _scripts/gerar_ranking_secao_estados.py [--uf SP]
Criado    : 2026-09-28
=============================================================================
"""
import argparse
import sys
from pathlib import Path

import duckdb

ANALISE = Path(__file__).resolve().parent.parent / "data" / "analise"
DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT = ANALISE / "ranking_estados"
PISO = 150
COMBS = [("presidente", 2, "presidente"), ("deputado federal", 1, "depfederal"),
         ("governador", 2, "governador")]
ANOS = (2014, 2018, 2022)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", nargs="+", help="UFs (padrao: todas presentes no CSV)")
    ap.add_argument("--cargo", nargs="+", choices=[c for _, _, c in COMBS],
                    help="cargos a gerar (padrao: todos)")
    args = ap.parse_args()

    if args.cargo:
        comb = [c for c in COMBS if c[2] in args.cargo]
    else:
        comb = COMBS
    print(f"combos: {[c[2] for c in comb]}")

    con = duckdb.connect(":memory:")
    con.execute(f"""CREATE TABLE z AS SELECT * FROM read_csv_auto(
        '{ANALISE.as_posix()}/campo_brasil_por_zona.csv', header=true)""")
    con.execute(f"""CREATE TABLE s AS SELECT * FROM read_csv_auto(
        '{ANALISE.as_posix()}/campo_brasil_por_secao.csv', header=true)""")
    con.execute(f"""ATTACH '{DB.as_posix()}' AS br (READ_ONLY)""")
    con.execute("""CREATE TABLE m AS
        SELECT DISTINCT cd_municipio_tse, nm_municipio_tse FROM br.dim_municipio""")

    if args.uf:
        ufs = [u.upper() for u in args.uf]
    else:
        ufs = [r[0] for r in con.execute(
            "SELECT DISTINCT sg_uf FROM s ORDER BY 1").fetchall()]
    print(f"UFs: {len(ufs)}")

    def build(nivel, uf, ano, cargou, turno, col, piso):
        extra = ", c.nr_secao" if nivel == "secao" else ""
        q = f"""
        SELECT c.sg_uf, c.ano_eletivo, c.cargo, c.nr_turno,
               c.cd_municipio_tse, m.nm_municipio_tse,
               c.nr_zona{extra},
               c.vot_esq, c.vot_cen, c.vot_dir, c.validos,
               ROUND(c.vot_dir*100.0/NULLIF(c.validos,0),2) AS share_dir,
               ROUND(c.vot_esq*100.0/NULLIF(c.validos,0),2) AS share_esq,
               ROUND(c.vot_cen*100.0/NULLIF(c.validos,0),2) AS share_cen,
               CASE WHEN c.vot_dir>c.vot_esq AND c.vot_dir>c.vot_cen THEN 'DIREITA'
                    WHEN c.vot_esq>c.vot_dir AND c.vot_esq>c.vot_cen THEN 'ESQUERDA'
                    WHEN c.vot_cen>c.vot_dir AND c.vot_cen>c.vot_esq THEN 'CENTRO'
                    ELSE 'EMPATE' END AS vencedor_campo
        FROM {tbl} c LEFT JOIN m USING (cd_municipio_tse)
        WHERE c.sg_uf = '{uf}' AND c.ano_eletivo = {ano}
          AND c.cargo = '{cargou}' AND c.nr_turno = {turno}
        """
        if piso:
            q += f" AND c.validos >= {piso}\n"
        q += f" ORDER BY {col} DESC, c.validos DESC"
        return q

    total = 0
    for nivel, tbl in (("zona", "z"), ("secao", "s")):
        for cargou, turno, cslug in comb:
            for ano in ANOS:
                for uf in ufs:
                    d = OUT / uf
                    d.mkdir(parents=True, exist_ok=True)
                    # governador: usa turno decisivo (T2 se houver dados, senao T1)
                    te = turno
                    if cargou == "governador":
                        tem_t2 = con.execute(
                            f"SELECT 1 FROM {tbl} WHERE sg_uf='{uf}' AND ano_eletivo={ano} "
                            f"AND cargo='governador' AND nr_turno=2 LIMIT 1").fetchone()
                        te = 2 if tem_t2 else 1
                    tag = f"{nivel}_{cslug}_{ano}_t{te}"
                    for bloco, col in (("direita", "share_dir"), ("esquerda", "share_esq")):
                        for suf, piso in (("", PISO), ("_abs", 0)):
                            col_ord = col if not suf else {"direita": "c.vot_dir", "esquerda": "c.vot_esq"}[bloco]
                            fn = d / f"ranking_{uf}_{tag}_{bloco}{suf}.csv"
                            if suf:
                                q = build(nivel, uf, ano, cargou, te, col_ord, 0)
                            else:
                                q = build(nivel, uf, ano, cargou, te, col, PISO)
                            with open(fn, "w", newline="", encoding="utf-8-sig") as f:
                                rows = con.execute(q).fetchall()
                                cols = [x[0] for x in con.description]
                                f.write(";".join(cols) + "\n")
                                for r in rows:
                                    f.write(";".join(str(x) for x in r) + "\n")
                            total += 1
                print(f"  {tag}: pronto")
        print(f"nivel {nivel}: ok")
    print(f"arquivos gerados: {total}")


if __name__ == "__main__":
    sys.exit(main())