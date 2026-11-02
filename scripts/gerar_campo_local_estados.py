#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_campo_local_estados.py
FUNCAO    : Campo politico (ESQ/CEN/DIR) por LOCAL de votacao, por UF,
            para presidente T2 e deputado federal T1 do ano 2022 (unico com
            endereco completo em dim_local_votacao). Junta endereco/bairro/
            cep/lat/lon do TSE. Grava por UF os CSVs de locais (todas linhas)
            e os TOP (locais/escolas) por DIREITA e ESQUERDA, % e total.
DEPENDE   : data/db/brasil.duckdb (vw_candidato_campo, dim_campo_partido,
            dim_municipio, dim_local_votacao).
SAIDAS    : data/analise/ranking_estados/{UF}/
              campo_local_{cargo}_{ano}_t{t}_{UF}.csv            (completo)
              top_local_{cargo}_{ano}_t{t}_{UF}_{dir|esq}.csv    (top 500 %)
              top_local_{cargo}_{ano}_t{t}_{UF}_{dir|esq}_abs.csv
USO       : python _scripts/gerar_campo_local_estados.py [--uf SP]
Criado    : 2026-09-28
=============================================================================
"""
import argparse
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT = Path(__file__).resolve().parent.parent / "data" / "analise" / "ranking_estados"
ANO = 2022
PISO = 150


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", nargs="+", help="UFs (padrao: todas)")
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    if args.uf:
        ufs = [u.upper() for u in args.uf]
    else:
        ufs = [r[0] for r in con.execute(
            "SELECT DISTINCT sg_uf FROM dim_municipio ORDER BY 1").fetchall()]

    combos = [("presidente", 2, "presidente"), ("deputado federal", 1, "depfederal")]
    total = 0
    for uf in ufs:
        for cargou, turno, cslug in combos:
            base_q = f"""
            WITH base AS (
                SELECT v.nr_turno, v.cd_municipio_tse, v.nr_zona,
                       v.nr_local_votacao,
                       COALESCE(NULLIF(TRIM(v.nm_local_votacao),''),'') AS local,
                       v.qt_votos,
                       COALESCE(c1.campo, c2.campo, p.campo) AS campo
                FROM fact_votacao_secao v
                LEFT JOIN dim_municipio m USING (cd_municipio_tse)
                {campo_join()}
                WHERE v.ano_eletivo = {ANO}
                  AND upper(v.ds_cargo) = '{cargou.upper()}'
                  AND v.nr_turno = {turno}
                  AND v.nr_votavel NOT IN (95, 96, 97)
                  AND m.sg_uf = '{uf}'
            )
            SELECT base.nr_turno, m.nm_municipio_tse, m.cd_municipio_tse,
                   base.nr_zona, base.nr_local_votacao,
                   base.local,
                   l.ds_endereco, l.nm_bairro, l.nr_cep,
                   l.nr_latitude, l.nr_longitude,
                   COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'ESQUERDA'),0) AS vot_esq,
                   COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'CENTRO'),0)   AS vot_cen,
                   COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'DIREITA'),0)  AS vot_dir,
                   SUM(base.qt_votos) AS validos
            FROM base
            JOIN dim_municipio m USING (cd_municipio_tse)
            LEFT JOIN dim_local_votacao l
                   ON l.ano_eletivo = {ANO} AND l.cd_municipio_tse = base.cd_municipio_tse
                  AND l.nr_zona = base.nr_zona AND l.nr_local_votacao = base.nr_local_votacao
            GROUP BY 1,2,3,4,5,6,7,8,9,10,11
            """
            d = OUT / uf
            d.mkdir(parents=True, exist_ok=True)
            tag = f"local_{cslug}_{ANO}_t{turno}"

            rows = con.execute(base_q + """ ORDER BY validos DESC""").fetchall()
            cols = [x[0] for x in con.description]
            fn_full = d / f"campo_{tag}_{uf}.csv"
            with open(fn_full, "w", newline="", encoding="utf-8-sig") as f:
                f.write(";".join(cols + ["share_dir", "share_esq", "share_cen",
                                         "vencedor_campo"]) + "\n")
                for r in rows:
                    c = dict(zip(cols, r))
                    v = c["validos"] or 0
                    sdir = 100.0 * (c["vot_dir"] or 0) / v if v else 0
                    sesq = 100.0 * (c["vot_esq"] or 0) / v if v else 0
                    scen = 100.0 * (c["vot_cen"] or 0) / v if v else 0
                    venc = ("DIREITA" if (c["vot_dir"] or 0) > (c["vot_esq"] or 0)
                            and (c["vot_dir"] or 0) > (c["vot_cen"] or 0)
                            else "ESQUERDA" if (c["vot_esq"] or 0) > (c["vot_dir"] or 0)
                            and (c["vot_esq"] or 0) > (c["vot_cen"] or 0)
                            else "CENTRO" if (c["vot_cen"] or 0) > (c["vot_dir"] or 0)
                            and (c["vot_cen"] or 0) > (c["vot_esq"] or 0)
                            else "EMPATE") if v else ""
                    f.write(";".join(str(x) for x in r) + ";"
                            f"{sdir:.2f};{sesq:.2f};{scen:.2f};" + venc + "\n")
            total += 1

            for bloco, col in (("direita", "vot_dir"), ("esquerda", "vot_esq")):
                for suf, piso in (("", PISO), ("_abs", 0)):
                    if suf:
                        sub = [r for r in rows]
                        sub.sort(key=lambda r: (-r[cols.index(col)], r[cols.index("validos")] or 0))
                    else:
                        sub = [r for r in rows if (r[cols.index("validos")] or 0) >= piso]
                        sub.sort(key=lambda r: (-100.0 * (r[cols.index(col)] or 0) /
                                                (r[cols.index("validos")] or 0),
                                                r[cols.index("validos")] or 0))
                    fn = d / f"top_{tag}_{uf}_{bloco}{suf}.csv"
                    with open(fn, "w", newline="", encoding="utf-8-sig") as f:
                        f.write(";".join(cols + ["share_dir", "share_esq", "share_cen",
                                                 "vencedor_campo"]) + "\n")
                        for r in sub[:500]:
                            c = dict(zip(cols, r))
                            v = c["validos"] or 0
                            sdir = 100.0 * (c["vot_dir"] or 0) / v if v else 0
                            sesq = 100.0 * (c["vot_esq"] or 0) / v if v else 0
                            scen = 100.0 * (c["vot_cen"] or 0) / v if v else 0
                            venc = ("DIREITA" if (c["vot_dir"] or 0) > (c["vot_esq"] or 0)
                                    and (c["vot_dir"] or 0) > (c["vot_cen"] or 0)
                                    else "ESQUERDA" if (c["vot_esq"] or 0) > (c["vot_dir"] or 0)
                                    and (c["vot_esq"] or 0) > (c["vot_cen"] or 0)
                                    else "CENTRO" if (c["vot_cen"] or 0) > (c["vot_dir"] or 0)
                                    and (c["vot_cen"] or 0) > (c["vot_esq"] or 0)
                                    else "EMPATE") if v else ""
                            f.write(";".join(str(x) for x in r) + ";"
                                    f"{sdir:.2f};{sesq:.2f};{scen:.2f};" + venc + "\n")
                    total += 1
            print(f"  {uf} {tag}: {len(rows):,} locais")
    print(f"arquivos: {total}")


if __name__ == "__main__":
    sys.exit(main())