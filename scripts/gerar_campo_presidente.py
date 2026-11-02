#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_campo_presidente.py
FUNCAO    : Campo politico (ESQUERDA/CENTRO/DIREITA) - Presidente (SP) 2014/2018/2022,
            por municipio / zona / secao / LOCAL, 1 registro por turno (1T e 2T).
            vencedor_campo = bloco com mais votos validos; shares sobre validos
            (NOMINAL+LEGENDA; 95/96 = BRANCO_NULO excluidos).
            Nivel "local" inclui lat/lon (join dim_local_votacao, ADR-008: chave
            com nr_zona) - base do Indice de Prioridade por local (2026-09-26).
DEPENDE   : banco com dim_candidato_map, dim_partido, fact_votacao_secao
            (camada analitica v007: candidatos de presidente carregados).
SAIDAS    : data/analise/campo_presidente_{ano}_por_{municipio,zona,secao,local}.csv
USO       :
    python _scripts/gerar_campo_presidente.py                     # 2014+2018+2022
    python _scripts/gerar_campo_presidente.py --ano 2022          # so 2022
    python _scripts/gerar_campo_presidente.py --nivel secao
=============================================================================
"""
import argparse
import duckdb

DB = r"D:/Dados_TSE/data/db/sao_paulo.duckdb"
OUT = "D:/Dados_TSE/data/analise/campo_presidente_{ano}_por_{nome}.csv"


def nivel_sql(grupo_cols, order_by, ano, geo=False):
    cols = ["v.nr_turno", "v.cd_municipio_tse"] + [f"v.{c}" for c in grupo_cols]
    select = ", ".join(cols)
    group = ", ".join(cols)
    geo_join, geo_cols = "", ""
    if geo:
        geo_join = f"""
        LEFT JOIN dim_local_votacao l
               ON l.ano_eletivo = {ano} AND l.cd_municipio_tse = v.cd_municipio_tse
              AND l.nr_zona = v.nr_zona AND l.nr_local_votacao = v.nr_local_votacao"""
        geo_cols = ", l.nm_local_votacao, l.ds_tipo_local, l.nr_latitude AS lat, l.nr_longitude AS lon"
    return f"""
COPY (
  WITH campo AS (
      SELECT {select},
             SUM(CASE WHEN COALESCE(k.campo,p.campo)='ESQUERDA' THEN v.qt_votos END) AS vot_esq,
             SUM(CASE WHEN COALESCE(k.campo,p.campo)='CENTRO'   THEN v.qt_votos END) AS vot_cen,
             SUM(CASE WHEN COALESCE(k.campo,p.campo)='DIREITA'  THEN v.qt_votos END) AS vot_dir,
             SUM(CASE WHEN v.nr_votavel NOT IN (95,96) THEN v.qt_votos END) AS validos
        FROM fact_votacao_secao v
        LEFT JOIN dim_candidato_map k
               ON k.ano_eletivo = v.ano_eletivo AND k.sq_candidato = v.sq_candidato
        LEFT JOIN dim_partido p ON p.nr_partido = v.nr_votavel
       WHERE v.ano_eletivo = {ano} AND UPPER(v.ds_cargo) = 'PRESIDENTE'
       GROUP BY {group}
  )
  SELECT {group}, m.cd_municipio_tse, m.nm_municipio_tse{geo_cols},
         COALESCE(v.vot_esq,0) AS vot_esq, COALESCE(v.vot_cen,0) AS vot_cen,
         COALESCE(v.vot_dir,0) AS vot_dir, COALESCE(v.validos,0) AS validos,
         ROUND(100.0*COALESCE(v.vot_esq,0)/NULLIF(v.validos,0),2) AS share_esq,
         ROUND(100.0*COALESCE(v.vot_cen,0)/NULLIF(v.validos,0),2) AS share_cen,
         ROUND(100.0*COALESCE(v.vot_dir,0)/NULLIF(v.validos,0),2) AS share_dir,
         CASE WHEN COALESCE(v.vot_esq,0) > COALESCE(v.vot_cen,0) AND COALESCE(v.vot_esq,0) > COALESCE(v.vot_dir,0) THEN 'ESQUERDA'
              WHEN COALESCE(v.vot_dir,0) > COALESCE(v.vot_cen,0) AND COALESCE(v.vot_dir,0) > COALESCE(v.vot_esq,0) THEN 'DIREITA'
              WHEN COALESCE(v.vot_cen,0) > COALESCE(v.vot_esq,0) AND COALESCE(v.vot_cen,0) > COALESCE(v.vot_dir,0) THEN 'CENTRO'
              ELSE 'EMPATE' END AS vencedor_campo
    FROM campo v JOIN dim_municipio m USING (cd_municipio_tse){geo_join}
   ORDER BY {order_by}
) TO '{OUT}'
  (FORMAT CSV, HEADER, DELIMITER ';')"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nivel", default="all",
                    choices=["all", "municipio", "zona", "secao", "local"])
    ap.add_argument("--ano", nargs="+", default=[2022, 2018, 2014], type=int,
                    help="anos eleitorais (padrao: 2022 2018 2014)")
    args = ap.parse_args()

    niveis = [("municipio", [], "m.nm_municipio_tse, nr_turno"),
              ("zona", ["nr_zona"], "m.nm_municipio_tse, nr_zona, nr_turno"),
              ("secao", ["nr_zona", "nr_secao"],
               "m.nm_municipio_tse, nr_zona, nr_secao, nr_turno"),
              ("local", ["nr_zona", "nr_local_votacao"],
               "m.nm_municipio_tse, nr_zona, nr_local_votacao, nr_turno")]
    if args.nivel == "all":
        niveis = [n for n in niveis if n[0] != "local"]  # "local" e pesado; pedir explicito
    else:
        niveis = [n for n in niveis if n[0] == args.nivel]

    con = duckdb.connect(DB, read_only=True)
    for ano in args.ano:
        por_ano = OUT.replace("{ano}", str(ano))
        for nome, grupo, order in niveis:
            sql = nivel_sql(grupo, order, ano, geo=(nome == "local")).replace("{nome}", nome)
            sql = sql.replace("{ano}", str(ano))
            con.execute(sql)
            n = con.execute(
                f"SELECT count(*) FROM read_csv('{por_ano.replace('{nome}', nome)}', "
                "delim=';', header=true)").fetchone()[0]
            print(f"{ano} -> {nome}: {n} linhas")

        if args.nivel in ("all", "municipio"):
            print(f"\nRESUMO {ano} por turno (cidades):")
            for r in con.execute(f"""
                SELECT nr_turno, vencedor_campo, count(*) FROM read_csv(
                  '{por_ano.replace('{nome}', 'municipio')}',
                  delim=';', header=true)
                GROUP BY 1,2 ORDER BY 1,2""").fetchall():
                print("  ", r)
    con.close()


if __name__ == "__main__":
    main()