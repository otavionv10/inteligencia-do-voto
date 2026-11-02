#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/ranking_secoes_deputado_federal.py
FUNCAO    : Ranking de secoes com mais votos de DIREITA (Deputado Federal,
            SP) por ano, turno 1 (unico do cargo). Duas metricas: total de
            votos dir e % de dir sobre validos (NOMINAL+LEGENDA; 95/96 excl).
            Usa o MESMO join de gerar_campo_deputado_federal.py (2014 por
            nr_votavel em dim_candidato_map_nr; 2018/22 por sq_candidato no
            dim_candidato incl. INAPTO). Inclui municipio, zona, secao, local.
SAIDAS    : data/analise/ranking_secao_direita_depfederal_{ano}_1t.csv
USO       :
    python _scripts/ranking_secoes_deputado_federal.py
=============================================================================
"""
import sys
from pathlib import Path

import duckdb

DB = r"D:/Dados_TSE/data/db/sao_paulo.duckdb"


def join_ano(ano):
    if ano == 2014:
        return """
        LEFT JOIN dim_candidato_map_nr n
               ON n.ano_eletivo = v.ano_eletivo
              AND n.nr_candidato = v.nr_votavel
              AND n.ds_cargo = 'DEPUTADO FEDERAL' AND n.grupo = 'SP'
        """, "COALESCE(n.campo, p.campo)"
    return """
        LEFT JOIN (SELECT c2.ano_eletivo, c2.sq_candidato, c2.nr_candidato,
                          upper(c2.ds_cargo) ds_cargo, c2.sg_uf, cp.campo
                     FROM (SELECT *, row_number() OVER
                                    (PARTITION BY ano_eletivo, sq_candidato
                                     ORDER BY nm_candidato) rn
                             FROM dim_candidato) c2
                     LEFT JOIN dim_campo_partido cp ON cp.nr_partido = c2.nr_partido
                    WHERE c2.rn = 1) k
          ON k.ano_eletivo = v.ano_eletivo AND k.sq_candidato = v.sq_candidato
        """, "COALESCE(k.campo, p.campo)"


def SQL(ano, order, out):
    join, campo = join_ano(ano)
    return f"""
COPY (
  WITH base AS (
      SELECT v.cd_municipio_tse, v.nr_zona, v.nr_secao,
             COALESCE(NULLIF(TRIM(v.nm_local_votacao), ''), '') AS local,
             SUM(CASE WHEN {campo}='ESQUERDA' THEN v.qt_votos END) AS vot_esq,
             SUM(CASE WHEN {campo}='CENTRO'   THEN v.qt_votos END) AS vot_cen,
             SUM(CASE WHEN {campo}='DIREITA'  THEN v.qt_votos END) AS vot_dir,
             SUM(CASE WHEN v.nr_votavel NOT IN (95,96) THEN v.qt_votos END) AS validos
        FROM fact_votacao_secao v
        {join}
        LEFT JOIN dim_partido p ON p.nr_partido = v.nr_votavel
       WHERE v.ano_eletivo = {ano} AND UPPER(v.ds_cargo) = 'DEPUTADO FEDERAL'
       GROUP BY 1,2,3,4
  )
  SELECT 'T1' AS turno, m.nm_municipio_tse, b.nr_zona, b.nr_secao, b.local,
         COALESCE(b.vot_esq,0) AS vot_esq, COALESCE(b.vot_cen,0) AS vot_cen,
         COALESCE(b.vot_dir,0) AS vot_dir, COALESCE(b.validos,0) AS validos,
         ROUND(100.0*COALESCE(b.vot_dir,0)/NULLIF(b.validos,0),2) AS share_dir_pct
    FROM base b JOIN dim_municipio m USING (cd_municipio_tse)
   ORDER BY {order}
) TO '{out}'
  (FORMAT CSV, HEADER, DELIMITER ';')
"""


def main():
    out_dir = Path(r"D:/Dados_TSE/data/analise")
    con = duckdb.connect(DB, read_only=True)
    for ano in (2014, 2018, 2022):
        base = out_dir / f"ranking_secao_direita_depfederal_{ano}_1t.csv"
        con.execute(SQL(ano, "share_dir_pct DESC, vot_dir DESC", base.as_posix()))
        con.execute(SQL(ano, "vot_dir DESC, share_dir_pct DESC",
                        f"{base.as_posix()[:-4]}_abs.csv".replace("\\", "/")))
        q = f"SELECT * FROM read_csv('{base.as_posix()}', delim=';', header=true)"
        print(f"=== TOP 10 secoes por % DIREITA Dep. Federal ({ano} T1) ===")
        for r in con.execute(f"{q} LIMIT 10").fetchall():
            print(f"  {r[9]:>6.2f}% de {r[8]:>6,} validos ({r[7]:>6,} DIR) | "
                  f"{r[1]}, zona {r[2]}, secao {r[3]} | {(r[4] or '')[:44]}")
        print(f"  ... piso >= 150 validos:")
        for r in con.execute(f"{q} WHERE validos >= 150 LIMIT 5").fetchall():
            print(f"  {r[9]:>6.2f}% de {r[8]:>6,} validos ({r[7]:>6,} DIR) | "
                  f"{r[1]}, zona {r[2]}, secao {r[3]} | {(r[4] or '')[:44]}")
        n = con.execute(
            f"SELECT count(*) FROM read_csv('{base.as_posix()}', delim=';', header=true)"
        ).fetchone()[0]
        print(f"  ({n:,} secoes)\n")
    con.close()
    print("OK: ranking_secao_direita_depfederal_*_1t.csv gerado")


if __name__ == "__main__":
    sys.exit(main())