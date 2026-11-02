#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_campo_municipio_por_ano_brasil.py
FUNCAO    : Campo politico (ESQ/CEN/DIR) por MUNICIPIO - BRASIL, por ANO,
            para presidente e deputado federal, 2014/2018/2022 (1 registro por
            turno). Mesmo schema dos antigos CSVs SP para alimentar
            gerar_grafico_tendencia.py (grafico de tendencia nacional), que
            antes so tinha os CSVs de SP.
OBS       : Diferente de gerar_campo_municipio_brasil.py (v035), que gera UM
            arquivo por cargo agrupado por UF (campo_municipio_brasil_por_cargo
            .csv) para os mapas choropleth. Este aqui gera UM arquivo por
            cargo+ano, no schema SP (nr_turno, cd_municipio_tse, ...
            vencedor_campo).
DEPENDE   : data/db/brasil.duckdb (vw_candidato_campo, dim_campo_partido,
            dim_municipio).
SAIDAS    : data/analise/campo_{cargo}_{ano}_por_municipio.csv
USO       : python _scripts/gerar_campo_municipio_por_ano_brasil.py
=============================================================================
"""
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT = Path(__file__).resolve().parent.parent / "data" / "analise"
ANOS = [2014, 2018, 2022]
CARGOS = {"presidente": "PRESIDENTE", "depfederal": "DEPUTADO FEDERAL"}


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


def gerar(con, cargo_slug, cargo_sql, ano):
    dest = OUT / f"campo_{cargo_slug}_{ano}_por_municipio.csv"
    sql = f"""
    COPY (
        WITH base AS (
            SELECT v.nr_turno, v.cd_municipio_tse,
                   v.qt_votos,
                   COALESCE(c1.campo, c2.campo, p.campo) AS campo
            FROM fact_votacao_secao v
            LEFT JOIN dim_municipio m USING (cd_municipio_tse)
            {campo_join()}
            WHERE v.ano_eletivo = {ano} AND UPPER(v.ds_cargo) = '{cargo_sql}'
              AND v.nr_votavel NOT IN (95, 96)
        )
        SELECT base.nr_turno, base.cd_municipio_tse,
               m.cd_municipio_tse AS cd_municipio_tse_1, m.nm_municipio_tse,
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
        GROUP BY 1,2,3,4
        ORDER BY base.nr_turno, m.nm_municipio_tse
    ) TO '{dest}'
      (FORMAT CSV, HEADER, DELIMITER ';');
    """
    con.execute(sql)
    n = con.execute(f"SELECT count(*) FROM read_csv('{dest}', delim=';', header=true)").fetchone()[0]
    print(f"{cargo_slug} {ano}: {n} linhas")


def main():
    con = duckdb.connect(str(DB), read_only=True)
    for slug, csql in CARGOS.items():
        for ano in ANOS:
            gerar(con, slug, csql, ano)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())