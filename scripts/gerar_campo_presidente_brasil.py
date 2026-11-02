#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_campo_presidente_brasil.py
FUNCAO    : Campo politico (ESQUERDA/CENTRO/DIREITA) - Presidente BRASIL
            (27 UFs) 2014/2018/2022, por LOCAL de votacao, 1 registro por
            turno. vencedor_campo = bloco com mais votos validos; shares
            sobre validos (95/96 = BRANCO_NULO excluidos, idem SP).
            Substitui gerar_campo_presidente.py (que apontava para
            sao_paulo.duckdb com dim_candidato_map/dim_partido) usando o
            join de campo padrao do projeto BR (vw_candidato_campo c1 por
            sq_candidato, fallback c2 por nr_candidato+cargo+UF e
            dim_campo_partido p quando sq_candidato<0).
DEPENDE   : data/db/brasil.duckdb (vw_candidato_campo, dim_campo_partido,
            dim_municipio, dim_local_votacao).
SAIDAS    : data/analise/campo_presidente_{ano}_por_local.csv (mesmo schema
            dos CSVs SP para nao quebrar q24_trajetoria).
USO       : python _scripts/gerar_campo_presidente_brasil.py [--ano 2022 2018 2014]
Criado    : 2026-09-28
=============================================================================
"""
import argparse
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT = Path(__file__).resolve().parent.parent / "data" / "analise"


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


def gerar(con, ano):
    sql = f"""
    COPY (
        WITH base AS (
            SELECT v.nr_turno, v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
                   v.qt_votos,
                   COALESCE(c1.campo, c2.campo, p.campo) AS campo
            FROM fact_votacao_secao v
            LEFT JOIN dim_municipio m USING (cd_municipio_tse)
            {campo_join()}
            WHERE v.ano_eletivo = {ano} AND UPPER(v.ds_cargo) = 'PRESIDENTE'
              AND v.nr_votavel NOT IN (95, 96)
        )
        SELECT base.nr_turno, base.cd_municipio_tse, base.nr_zona, base.nr_local_votacao,
               m.cd_municipio_tse AS cd_municipio_tse_1, m.nm_municipio_tse,
               l.nm_local_votacao, l.ds_tipo_local, l.nr_latitude AS lat, l.nr_longitude AS lon,
               COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'ESQUERDA'),0) AS vot_esq,
               COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'CENTRO'),0)   AS vot_cen,
               COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'DIREITA'),0)  AS vot_dir,
               SUM(base.qt_votos) AS validos,
               ROUND(100.0 * COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'ESQUERDA'),0)
                      / NULLIF(SUM(base.qt_votos),0), 2) AS share_esq,
               ROUND(100.0 * COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'CENTRO'),0)
                      / NULLIF(SUM(base.qt_votos),0), 2) AS share_cen,
               ROUND(100.0 * COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'DIREITA'),0)
                      / NULLIF(SUM(base.qt_votos),0), 2) AS share_dir,
               CASE
                 WHEN SUM(base.qt_votos) FILTER (WHERE base.campo = 'DIREITA') >
                      GREATEST(COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'CENTRO'),0),
                               COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'ESQUERDA'),0))
                      THEN 'DIREITA'
                 WHEN SUM(base.qt_votos) FILTER (WHERE base.campo = 'ESQUERDA') >
                      GREATEST(COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'CENTRO'),0),
                               COALESCE(SUM(base.qt_votos) FILTER (WHERE base.campo = 'DIREITA'),0))
                      THEN 'ESQUERDA'
                 ELSE 'CENTRO'
               END AS vencedor_campo
        FROM base
        JOIN dim_municipio m USING (cd_municipio_tse)
        LEFT JOIN dim_local_votacao l
               ON l.ano_eletivo = {ano}
              AND l.cd_municipio_tse = base.cd_municipio_tse
              AND l.nr_zona = base.nr_zona
              AND l.nr_local_votacao = base.nr_local_votacao
        GROUP BY 1,2,3,4,5,6,7,8,9,10
        ORDER BY base.nr_turno, m.nm_municipio_tse, base.nr_zona, base.nr_local_votacao
    ) TO '{OUT / ("campo_presidente_%d_por_local.csv" % ano)}'
      (FORMAT CSV, HEADER, DELIMITER ';');
    """
    con.execute(sql)
    n = con.execute(f"""
        SELECT count(*) FROM read_csv('{OUT / ("campo_presidente_%d_por_local.csv" % ano)}',
        delim=';', header=true)""").fetchone()[0]
    print(f"{ano} -> campo_presidente_por_local: {n} linhas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", nargs="+", default=[2022, 2018, 2014], type=int)
    args = ap.parse_args()
    con = duckdb.connect(str(DB), read_only=True)
    for ano in sorted(args.ano, reverse=True):
        gerar(con, ano)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())