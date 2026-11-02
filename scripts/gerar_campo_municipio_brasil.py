#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_campo_municipio_brasil.py
FUNCAO    : Campo politico (ESQUERDA/CENTRO/DIREITA) por MUNICIPIO, no banco
            BRASIL, p/ PRESIDENTE + GOVERNADOR + DEPUTADO FEDERAL, 2014/18/22,
            1 registro por turno. vencedor_campo = bloco com mais validos;
            shares sobre validos (NOMINAL+LEGENDA; 95/96/97 = BRANCO_NULO
            excluidos). agrupado por sg_uf para permitir mapa por estado.
DEPENDE   : data/db/brasil.duckdb com camada analitica
            vw_candidato_campo + dim_campo_partido + dim_municipio.
SAIDAS    : data/analise/campo_municipio_brasil_por_cargo.csv (TODOS estados)
USO       : python _scripts/gerar_campo_municipio_brasil.py [UF UF ...]
=============================================================================
"""
import csv
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT = Path(__file__).resolve().parent.parent / "data" / "analise" / "campo_municipio_brasil_por_cargo.csv"
ANOS = (2014, 2018, 2022)
CARGOS = ("PRESIDENTE", "GOVERNADOR", "DEPUTADO FEDERAL")


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
    ufs = [u.upper() for u in sys.argv[1:]]
    con = duckdb.connect(str(DB), read_only=True)

    base = f"""
        SELECT v.ano_eletivo,
               COALESCE(m.sg_uf, 'ZZ') AS sg_uf,
               v.cd_municipio_tse,
               v.nr_turno,
               upper(v.ds_cargo) AS cargo,
               v.qt_votos,
               COALESCE(c1.campo, c2.campo, p.campo) AS campo
        FROM fact_votacao_secao v
        LEFT JOIN dim_municipio m USING (cd_municipio_tse)
        {campo_join()}
        WHERE v.nr_votavel NOT IN (95, 96, 97)
    """
    cond_uf = f" AND m.sg_uf IN ({','.join('?' * len(ufs))})" if ufs else ""
    args = ufs if ufs else None

    rows = con.execute(f"""
        WITH base AS (
            {base}{cond_uf}
        )
        SELECT sg_uf, cd_municipio_tse, ano_eletivo, lower(cargo) AS cargo, nr_turno,
               COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'ESQUERDA'), 0) AS vot_esq,
               COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'CENTRO'),   0) AS vot_cen,
               COALESCE(SUM(qt_votos) FILTER (WHERE campo = 'DIREITA'),  0) AS vot_dir,
               COALESCE(SUM(qt_votos) FILTER (WHERE campo IS NULL),     0) AS vot_sem_campo,
               SUM(qt_votos) AS validos
        FROM base
        GROUP BY sg_uf, cd_municipio_tse, ano_eletivo, cargo, nr_turno
        ORDER BY sg_uf, cd_municipio_tse, ano_eletivo, nr_turno
    """, args).fetchall()
    print(f"linhas municipio agregadas: {len(rows)}")

    out_dir = OUT.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sg_uf", "cd_municipio_tse", "ano_eletivo", "cargo", "nr_turno",
                    "vot_esq", "vot_cen", "vot_dir", "vot_sem_campo", "validos",
                    "share_esq", "share_cen", "share_dir", "vencedor_campo"])
        for r in rows:
            uf, tse, ano, carg, turno, esq, cen, dir_, sem, validos = r
            share = lambda x: (x / validos * 100) if validos else 0.0
            vencedor = ("DIREITA" if dir_ > esq and dir_ > cen
                        else "ESQUERDA" if esq > dir_ and esq > cen
                        else "CENTRO" if cen > dir_ and cen > esq
                        else "EMPATE") if validos else ""
            w.writerow([uf, tse, ano, carg, turno, esq, cen, dir_, sem, validos,
                        round(share(esq), 2), round(share(cen), 2), round(share(dir_), 2), vencedor])
    print(f"OK: {OUT}")

    uf_set = sorted({r[0] for r in rows})
    print("UFs:", uf_set)
    con.close()


if __name__ == "__main__":
    sys.exit(main())