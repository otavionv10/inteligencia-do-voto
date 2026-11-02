#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/ranking_secoes_direita.py
FUNCAO    : Ranking de secoes com mais votos de DIREITA (presidente, SP) por ano,
            turno 2 (decisivo). Duas metricas: total de votos dir e % de dir sobre
            validos (95/96 excluidos). Inclui municipio, zona, secao e local.
SAIDAS    : data/analise/ranking_secao_direita_{ano}_2t.csv (top 500 por metrica)
USO       :
    python _scripts/ranking_secoes_direita.py
"""
import sys
from pathlib import Path

import duckdb

DB = r"D:/Dados_TSE/data/db/sao_paulo.duckdb"

SQL = """
COPY (
  WITH campo AS (
      SELECT v.nr_turno, v.cd_municipio_tse, v.nr_zona, v.nr_secao,
             COALESCE(NULLIF(TRIM(v.nm_local_votacao), ''), '') AS local,
             SUM(CASE WHEN COALESCE(k.campo,p.campo)='ESQUERDA' THEN v.qt_votos END) AS vot_esq,
             SUM(CASE WHEN COALESCE(k.campo,p.campo)='CENTRO'   THEN v.qt_votos END) AS vot_cen,
             SUM(CASE WHEN COALESCE(k.campo,p.campo)='DIREITA'  THEN v.qt_votos END) AS vot_dir,
             SUM(CASE WHEN v.nr_votavel NOT IN (95,96) THEN v.qt_votos END) AS validos
        FROM fact_votacao_secao v
        LEFT JOIN dim_candidato_map k
               ON k.ano_eletivo = v.ano_eletivo AND k.sq_candidato = v.sq_candidato
        LEFT JOIN dim_partido p ON p.nr_partido = v.nr_votavel
       WHERE v.ano_eletivo = {ano} AND UPPER(v.ds_cargo) = 'PRESIDENTE' AND v.nr_turno = 2
       GROUP BY 1,2,3,4,5
  )
  SELECT 'T2' AS turno, m.nm_municipio_tse, c.nr_zona, c.nr_secao, c.local,
         COALESCE(c.vot_esq,0) AS vot_esq, COALESCE(c.vot_cen,0) AS vot_cen,
         COALESCE(c.vot_dir,0) AS vot_dir, COALESCE(c.validos,0) AS validos,
         ROUND(100.0*COALESCE(c.vot_dir,0)/NULLIF(c.validos,0),2) AS share_dir_pct
    FROM campo c JOIN dim_municipio m USING (cd_municipio_tse)
   ORDER BY {order}
) TO '{out_dir}/ranking_secao_direita_{ano}_2t{ext}.csv'
  (FORMAT CSV, HEADER, DELIMITER ';')
"""


def _p(con, r):
    local = (r[4] or "").rstrip()
    print(f"  {r[5]:>6,} votos dir ({r[7]:>5.1f}% de {r[6]:,}) | "
          f"{r[1]}, zona {r[2]}, secao {r[3]} | {local[:44]}")


def main():
    out_dir = Path(r"D:/Dados_TSE/data/analise")
    con = duckdb.connect(DB, read_only=True)
    for ano in (2014, 2018, 2022):
        con.execute(SQL.format(ano=ano, out_dir=out_dir, order="share_dir_pct DESC, vot_dir DESC", ext=""))
        n_share = con.execute(
            f"SELECT count(*) FROM read_csv('{out_dir}/ranking_secao_direita_{ano}_2t.csv', "
            "delim=';', header=true)").fetchone()[0]
        con.execute(SQL.format(ano=ano, out_dir=out_dir, order="vot_dir DESC, share_dir_pct DESC", ext="_abs"))
        n_abs = con.execute(
            f"SELECT count(*) FROM read_csv('{out_dir}/ranking_secao_direita_{ano}_2t_abs.csv', "
            "delim=';', header=true)").fetchone()[0]
        print(f"{ano} -> ranking por %: {n_share} | por total: {n_abs}")
        q = f"""
            SELECT turno, nm_municipio_tse, nr_zona, nr_secao, local,
                   vot_dir, validos, share_dir_pct
              FROM read_csv('{out_dir}/ranking_secao_direita_{ano}_2t.csv',
                            delim=';', header=true)"""
        print(f"=== TOP 10 por % de DIREITA ({ano} T2, total) ===")
        for r in con.execute(f"{q} LIMIT 10").fetchall():
            _p(con, r)
        print(f"=== TOP 10 por % de DIREITA ({ano} T2, piso >= 150 validos) ===")
        for r in con.execute(f"{q} WHERE validos >= 150 LIMIT 10").fetchall():
            _p(con, r)
        print(f"=== TOP 10 por TOTAL de votos de DIREITA ({ano} T2) ===")
        for r in con.execute(
                q + " ORDER BY vot_dir DESC, share_dir_pct DESC LIMIT 10").fetchall():
            _p(con, r)
    con.close()
    print("OK: ranking gerado em data/analise/ranking_secao_direita_*.csv")


if __name__ == "__main__":
    sys.exit(main())