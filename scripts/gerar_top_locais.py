#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_top_locais.py
FUNCAO    : TOP LOCAIS DE VOTACAO (1 por linha) ordenados pelos votos do PROPRIO
            local (nao da zona), com endereco completo e tipo do local.
            Excel com abas "Top Direita" e "Top Esquerda".
FONTES    : data/db/sao_paulo.duckdb (votos por local)
            data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv (endereco+tipo por local)
SAIDA     : data/analise/TOP Locais de Votacao por Votos - {cargo} (Direita e Esquerda).xlsx
USO       : python _scripts/gerar_top_locais.py [presidente|depfederal] [ano]
"""
import csv
import sys
from pathlib import Path

import duckdb

ANALISE = Path(r"D:/Dados_TSE/data/analise")
DB = "D:/Dados_TSE/data/db/sao_paulo.duckdb"
CARGOS = {"presidente": ("PRESIDENTE", 2, "Presidente"), "presid": ("PRESIDENTE", 2, "Presidente"),
          "pres": ("PRESIDENTE", 2, "Presidente"),
          "depfederal": ("DEPUTADO FEDERAL", 1, "Deputado Federal"), "dep": ("DEPUTADO FEDERAL", 1, "Deputado Federal")}


def main():
    cargo = (sys.argv[1] if len(sys.argv) > 1 else "presidente").lower()
    ano = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
    cargo_up, turno, rotulo = CARGOS.get(cargo, ("PRESIDENTE", 2, "Presidente"))

    # endereco+tipo por (municipio, zona, local)
    end = {}
    src = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    for r in csv.DictReader(src.open(encoding="utf-8-sig"), delimiter=";"):
        end[(r["cd_municipio_tse"], int(r["nr_zona"]), int(r["nr_local_votacao"]))] = r

    # votos do PROPRIO local (cargo/turno)
    con = duckdb.connect(DB, read_only=True)
    q = f"""
      SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='ESQUERDA'),0) esq,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='CENTRO'),0) cen,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='DIREITA'),0) dir,
             COALESCE(SUM(v.qt_votos) FILTER (WHERE v.nr_votavel NOT IN (95,96,97)),0) val
        FROM fact_votacao_secao v
        LEFT JOIN vw_candidato_campo c ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
       WHERE v.ano_eletivo={ano} AND UPPER(v.ds_cargo)='{cargo_up}' AND v.nr_turno={turno}
       GROUP BY 1,2,3
    """
    linhas = []
    for mun, zona, local, esq, cen, dire, val in con.execute(q).fetchall():
        e = end.get((mun, zona, local), {})
        pdir = round(100.0 * dire / val, 2) if val else 0.0
        pesq = round(100.0 * esq / val, 2) if val else 0.0
        venc = max((("DIREITA", dire), ("CENTRO", cen), ("ESQUERDA", esq)), key=lambda t: t[1])[0]
        linhas.append({
            "cd_municipio_tse": mun, "nm_municipio": e.get("nm_municipio", ""),
            "nr_zona": zona, "nr_local_votacao": local,
            "nm_local_votacao": e.get("nm_local_votacao", ""), "tipo_local": e.get("tipo_local", ""),
            "logradouro": e.get("logradouro", ""), "numero": e.get("numero", ""),
            "nm_bairro": e.get("nm_bairro", ""), "nr_cep": e.get("nr_cep", ""),
            "lat": e.get("lat", ""), "lon": e.get("lon", ""),
            "vot_esq": esq, "vot_cen": cen, "vot_dir": dire, "validos": val,
            "pct_dir": pdir, "pct_esq": pesq, "vencedor": venc,
        })
    print(f"{rotulo}: {len(linhas):,} locais de votacao")

    cols = ["rank", "cd_municipio_tse", "nm_municipio", "nr_zona", "nr_local_votacao",
            "nm_local_votacao", "tipo_local", "logradouro", "numero", "nm_bairro", "nr_cep",
            "lat", "lon", "vot_esq", "vot_cen", "vot_dir", "validos", "pct_dir", "pct_esq", "vencedor"]

    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    for aba, chave in (("Top Direita", "vot_dir"), ("Top Esquerda", "vot_esq")):
        ws = wb.create_sheet(aba); ws.append(cols)
        for i, d in enumerate(sorted(linhas, key=lambda d: d[chave], reverse=True), 1):
            d = {**d, "rank": i}
            ws.append([d[c] for c in cols])
        ws.freeze_panes = "A2"
    out = ANALISE / f"TOP Locais de Votacao por Votos - {rotulo} (Direita e Esquerda).xlsx"
    wb.save(out)
    print(f"OK: {out.name} | abas {wb.sheetnames}")

    def a(s): return str(s).encode("ascii", "replace").decode()
    print(f"topo DIREITA ({rotulo}) - votos do PROPRIO local:")
    for d in sorted(linhas, key=lambda d: d["vot_dir"], reverse=True)[:5]:
        print(f"  {a(d['nm_municipio'])} | {a(d['nm_local_votacao'])[:28]} | "
              f"{a(d['logradouro'])[:22]} {d['numero']} | DIR {d['vot_dir']} ({d['pct_dir']}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
