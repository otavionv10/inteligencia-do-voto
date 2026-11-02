#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_ranking_setor.py
FUNCAO    : TOP SETORES CENSITARIOS por votos de direita/esquerda, com a LISTA
            das escolas de cada setor. Excel com 3 abas:
            "Top Direita", "Top Esquerda" (1 linha por setor, ordenado por votos
            absolutos do cargo) e "Escolas por setor" (1 linha por escola/local).
FONTES    : data/db/sao_paulo.duckdb (votos por local, dep 1T e pres 2T)
            data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv (local->setor+endereco)
SAIDA     : data/analise/TOP Setores por Votos - {cargo} (Direita e Esquerda) com Escolas.xlsx
USO       : python _scripts/gerar_ranking_setor.py [presidente|depfederal] [ano]
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ANALISE = Path(r"D:/Dados_TSE/data/analise")
DB = "D:/Dados_TSE/data/db/sao_paulo.duckdb"
CARGOS = {"presidente": "pres", "presid": "pres", "pres": "pres",
          "depfederal": "dep", "deputado": "dep", "dep": "dep"}
ROT = {"pres": "Presidente", "dep": "Deputado Federal"}


def setor15(s):
    d = re.sub(r"\D", "", s or "")
    return d[:15] if len(d) >= 15 else ""


def modal(lst):
    c = defaultdict(int)
    for x in lst:
        if x:
            c[x] += 1
    return max(c.items(), key=lambda kv: kv[1])[0] if c else ""


def main():
    cargo = CARGOS.get((sys.argv[1] if len(sys.argv) > 1 else "presidente").lower(), "pres")
    ano = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
    rotulo = ROT[cargo]

    # votos por local (dep 1T + pres 2T)
    con = duckdb.connect(DB, read_only=True)
    vloc = {}
    for r in con.execute(f"""
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='DIREITA'),0) dep_dir,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='ESQUERDA'),0) dep_esq,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND v.nr_votavel NOT IN (95,96,97)),0) dep_val,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='DIREITA'),0) pres_dir,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='ESQUERDA'),0) pres_esq,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND v.nr_votavel NOT IN (95,96,97)),0) pres_val
        FROM fact_votacao_secao v
        LEFT JOIN vw_candidato_campo c ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
       WHERE v.ano_eletivo={ano} GROUP BY 1,2,3
    """).fetchall():
        vloc[(r[0], r[1], r[2])] = r[3:]

    # local -> setor + endereco (do arquivo enriquecido)
    src = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    locais = list(csv.DictReader(src.open(encoding="utf-8-sig"), delimiter=";"))

    # agrega por setor
    S = defaultdict(lambda: {"dep_dir": 0, "dep_esq": 0, "dep_val": 0, "pres_dir": 0, "pres_esq": 0,
                             "pres_val": 0, "mun": [], "bairro": [], "escolas": [], "n": 0})
    long_rows = []
    for r in locais:
        cs = setor15(r.get("cnefe_cod_setor", ""))
        if not cs:
            continue
        key = (r["cd_municipio_tse"], int(r["nr_zona"]), int(r["nr_local_votacao"]))
        v = vloc.get(key)
        if not v:
            continue
        dd, de, dv, pdr, pe, pvv = v
        a = S[cs]
        a["dep_dir"] += dd; a["dep_esq"] += de; a["dep_val"] += dv
        a["pres_dir"] += pdr; a["pres_esq"] += pe; a["pres_val"] += pvv
        a["mun"].append(r.get("nm_municipio", "")); a["bairro"].append(r.get("nm_bairro", ""))
        a["n"] += 1
        end = f"{r.get('logradouro','')}, {r.get('numero','')}".strip(", ")
        a["escolas"].append(f"{r.get('nm_local_votacao','')}: {end}")
        long_rows.append({
            "cod_setor": cs, "nm_municipio": r.get("nm_municipio", ""), "nr_zona": r["nr_zona"],
            "nr_local_votacao": r["nr_local_votacao"], "nm_local_votacao": r.get("nm_local_votacao", ""),
            "tipo_local": r.get("tipo_local", ""), "logradouro": r.get("logradouro", ""),
            "numero": r.get("numero", ""), "nm_bairro": r.get("nm_bairro", ""), "nr_cep": r.get("nr_cep", ""),
            "lat": r.get("lat", ""), "lon": r.get("lon", ""),
            "loc_pres_dir": pdr, "loc_pres_esq": pe, "loc_dep_dir": dd, "loc_dep_esq": de,
        })

    def pct(p, t): return round(100.0 * p / t, 1) if t else 0.0
    setores = []
    for cs, a in S.items():
        setores.append({
            "cod_setor": cs, "municipio": modal(a["mun"]), "bairro": modal(a["bairro"]),
            "qt_escolas": a["n"],
            "pres_vot_dir": a["pres_dir"], "pres_vot_esq": a["pres_esq"], "pres_validos": a["pres_val"],
            "pres_pct_dir": pct(a["pres_dir"], a["pres_val"]), "pres_pct_esq": pct(a["pres_esq"], a["pres_val"]),
            "pres_vencedor": "DIREITA" if a["pres_dir"] >= a["pres_esq"] else "ESQUERDA",
            "dep_vot_dir": a["dep_dir"], "dep_vot_esq": a["dep_esq"], "dep_validos": a["dep_val"],
            "dep_pct_dir": pct(a["dep_dir"], a["dep_val"]), "dep_pct_esq": pct(a["dep_esq"], a["dep_val"]),
            "escolas": " | ".join(a["escolas"]),
        })
    print(f"setores com voto: {len(setores):,} | escolas: {len(long_rows):,}")

    # rank do setor pelo cargo escolhido + enriquece cada local com stats do setor
    setores.sort(key=lambda d: d[f"{cargo}_vot_dir"], reverse=True)
    rank = {d["cod_setor"]: i + 1 for i, d in enumerate(setores)}
    smap = {d["cod_setor"]: d for d in setores}
    for d in long_rows:
        s = smap.get(d["cod_setor"], {})
        d["rank_direita_setor"] = rank.get(d["cod_setor"], "")
        d["setor_vot_dir"] = s.get(f"{cargo}_vot_dir", "")
        d["setor_pct_dir"] = s.get(f"{cargo}_pct_dir", "")
        d["setor_pct_esq"] = s.get(f"{cargo}_pct_esq", "")

    scols = ["cod_setor", "municipio", "bairro", "qt_escolas",
             "pres_vot_dir", "pres_vot_esq", "pres_validos", "pres_pct_dir", "pres_pct_esq", "pres_vencedor",
             "dep_vot_dir", "dep_vot_esq", "dep_validos", "dep_pct_dir", "dep_pct_esq", "escolas"]
    lcols = ["cod_setor", "nm_municipio", "nr_zona", "nr_local_votacao", "nm_local_votacao",
             "tipo_local", "logradouro", "numero", "nm_bairro", "nr_cep", "lat", "lon",
             "loc_pres_dir", "loc_pres_esq", "loc_dep_dir", "loc_dep_esq"]
    kd, ke = f"{cargo}_vot_dir", f"{cargo}_vot_esq"

    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    for aba, chave in (("Top Direita", kd), ("Top Esquerda", ke)):
        ws = wb.create_sheet(aba); ws.append(scols)
        for d in sorted(setores, key=lambda d: d[chave], reverse=True):
            ws.append([d[c] for c in scols])
        ws.freeze_panes = "A2"
    ws = wb.create_sheet("Escolas por setor"); ws.append(lcols)
    for d in sorted(long_rows, key=lambda d: (d["cod_setor"], int(d["nr_local_votacao"]))):
        ws.append([d[c] for c in lcols])
    ws.freeze_panes = "A2"
    out = ANALISE / f"TOP Setores por Votos - {rotulo} (Direita e Esquerda) com Escolas.xlsx"
    wb.save(out)
    print(f"OK: {out.name} | abas {wb.sheetnames}")

    def a_(s): return str(s).encode("ascii", "replace").decode()
    print(f"topo DIREITA ({rotulo}):")
    for d in sorted(setores, key=lambda d: d[kd], reverse=True)[:5]:
        print(f"  setor {d['cod_setor']} {a_(d['municipio'])} | {cargo}_vot_dir={d[kd]} "
              f"({d[cargo+'_pct_dir']}%) | {d['qt_escolas']} escola(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
