#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_ranking_secao.py
FUNCAO    : TOP SECOES (o grao mais fino - a urna) por votos de direita/esquerda,
            com o ENDERECO do local (varias secoes compartilham o mesmo local).
            Excel com 2 abas: "Top Direita" e "Top Esquerda" (votos absolutos).
FONTES    : data/db/sao_paulo.duckdb (fact_votacao_secao + vw_candidato_campo)
            data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv (endereco por local)
SAIDA     : data/analise/TOP Secoes por Votos - {cargo} (Direita e Esquerda) com Enderecos.xlsx
USO       : python _scripts/gerar_ranking_secao.py [presidente|depfederal] [ano]
"""
import csv
import sys
from pathlib import Path

import duckdb

ANALISE = Path(r"D:/Dados_TSE/data/analise")
DB = "D:/Dados_TSE/data/db/sao_paulo.duckdb"
CARGOS = {"presidente": ("PRESIDENTE", 2, "Presidente"),
          "presid": ("PRESIDENTE", 2, "Presidente"),
          "depfederal": ("DEPUTADO FEDERAL", 1, "Deputado Federal"),
          "dep": ("DEPUTADO FEDERAL", 1, "Deputado Federal")}


def main():
    cargo = (sys.argv[1] if len(sys.argv) > 1 else "presidente").lower()
    ano = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
    cargo_up, turno, rotulo = CARGOS.get(cargo, ("PRESIDENTE", 2, "Presidente"))

    # enderecos por (municipio, zona, local)
    end = {}
    src = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    if not src.exists():
        src = ANALISE / f"enderecos_locais_zona_sp_{ano}.csv"
    for r in csv.DictReader(src.open(encoding="utf-8-sig"), delimiter=";"):
        end[(r["cd_municipio_tse"], int(r["nr_zona"]), int(r["nr_local_votacao"]))] = r

    con = duckdb.connect(DB, read_only=True)
    q = f"""
      SELECT v.cd_municipio_tse, v.nr_zona, v.nr_secao, max(v.nr_local_votacao) AS nr_local,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='ESQUERDA'),0) AS vot_esq,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='CENTRO'),0)   AS vot_cen,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='DIREITA'),0)  AS vot_dir,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE v.nr_votavel NOT IN (95,96,97)),0) AS validos
        FROM fact_votacao_secao v
        LEFT JOIN vw_candidato_campo c
               ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
       WHERE v.ano_eletivo={ano} AND UPPER(v.ds_cargo)='{cargo_up}' AND v.nr_turno={turno}
       GROUP BY 1,2,3
    """
    linhas = []
    for mun, zona, secao, local, esq, cen, dire, val in con.execute(q).fetchall():
        e = end.get((mun, zona, local), {})
        pdir = round(100.0 * dire / val, 2) if val else 0.0
        pesq = round(100.0 * esq / val, 2) if val else 0.0
        venc = max((("DIREITA", dire), ("CENTRO", cen), ("ESQUERDA", esq)), key=lambda t: t[1])[0]
        linhas.append({
            "nr_zona": zona, "cd_municipio_tse": mun, "nm_municipio": e.get("nm_municipio", ""),
            "nr_secao": secao, "nr_local_votacao": local,
            "nm_local_votacao": e.get("nm_local_votacao", ""), "tipo_local": e.get("tipo_local", ""),
            "logradouro": e.get("logradouro", ""), "numero": e.get("numero", ""),
            "nm_bairro": e.get("nm_bairro", ""), "nr_cep": e.get("nr_cep", ""),
            "lat": e.get("lat", ""), "lon": e.get("lon", ""),
            "vot_esq": esq, "vot_cen": cen, "vot_dir": dire, "validos": val,
            "pct_dir": pdir, "pct_esq": pesq, "vencedor": venc,
        })
    print(f"{rotulo}: {len(linhas):,} secoes")

    cols = ["nr_zona", "cd_municipio_tse", "nm_municipio", "nr_secao", "nr_local_votacao",
            "nm_local_votacao", "tipo_local", "logradouro", "numero", "nm_bairro", "nr_cep",
            "lat", "lon", "vot_esq", "vot_cen", "vot_dir", "validos", "pct_dir", "pct_esq", "vencedor"]

    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    for aba, chave in (("Top Direita", "vot_dir"), ("Top Esquerda", "vot_esq")):
        ws = wb.create_sheet(aba); ws.append(cols)
        for d in sorted(linhas, key=lambda d: d[chave], reverse=True):
            ws.append([d[c] for c in cols])
        ws.freeze_panes = "A2"
    out = ANALISE / f"TOP Secoes por Votos - {rotulo} (Direita e Esquerda) com Enderecos.xlsx"
    wb.save(out)
    mb = out.stat().st_size / 1048576
    print(f"OK: {out.name}  | abas {wb.sheetnames} | {mb:.1f} MB")

    def a(s): return str(s).encode("ascii", "replace").decode()
    print("topo DIREITA:")
    for d in sorted(linhas, key=lambda d: d["vot_dir"], reverse=True)[:3]:
        print(f"  z{d['nr_zona']} {a(d['nm_municipio'])} secao {d['nr_secao']} @ {a(d['nm_local_votacao'])[:24]} "
              f"| DIR {d['vot_dir']} ({d['pct_dir']}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
