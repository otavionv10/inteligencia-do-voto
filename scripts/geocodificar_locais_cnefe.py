#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/geocodificar_locais_cnefe.py
FUNCAO    : Preenche a lat/lon dos locais de votacao SEM geo (placeholder -1 na
            fonte do TSE) usando a base CNEFE (D:/dados_cnefe/sp_geo.duckdb,
            22,6M enderecos), casando por camadas (combina variacoes de busca):
              1. CEP + numero exato          -> media das coords
              2. CEP + numero mais proximo    -> coord do vizinho de numero
              3. CEP (centroide do CEP)        -> mediana das coords do CEP
            Gera locais enriquecidos + recomputa o resumo por zona (centroide),
            agora praticamente 100%.
ENTRADA   : data/analise/locais_por_zona_sp_{ano}.csv  (de gerar_locais_por_zona.py)
CNEFE     : ATTACH read-only (nao copia os 2,4 GB)
SAIDAS    : data/analise/locais_por_zona_sp_{ano}_geo.csv  (+ fonte_geo)
            data/analise/zonas_sp_{ano}_resumo.csv          (sobrescreve c/ geo cheio)
USO       : python _scripts/geocodificar_locais_cnefe.py [ano]   (default 2022)
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

import duckdb

BASE = Path(r"D:/Dados_TSE")
DB = BASE / "data" / "db" / "sao_paulo.duckdb"
CNEFE = "D:/dados_cnefe/sp_geo.duckdb"
ANALISE = BASE / "data" / "analise"
SP_LAT, SP_LON = (-25.6, -19.4), (-53.6, -44.0)


def num_de(endereco):
    m = re.findall(r"(\d+)", endereco or "")
    return int(m[-1]) if m else None


def cep8(v):
    d = re.sub(r"\D", "", v or "")
    return d.zfill(8) if d else None


def valid(la, lo):
    return la is not None and SP_LAT[0] <= la <= SP_LAT[1] and SP_LON[0] <= lo <= SP_LON[1]


def main():
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    src = ANALISE / f"locais_por_zona_sp_{ano}.csv"
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig"), delimiter=";"))
    faltam = [r for r in rows if not r["lat"]]
    print(f"{len(rows):,} locais | sem geo: {len(faltam)}")

    ceps = {cep8(r["nr_cep"]) for r in faltam if cep8(r["nr_cep"])}
    print(f"CEPs a consultar no CNEFE: {len(ceps)}")

    # 1 consulta unica: todos os enderecos CNEFE dos CEPs necessarios
    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{CNEFE}' AS cnefe (READ_ONLY)")
    con.execute("CREATE TEMP TABLE ceps(cep VARCHAR)")
    con.executemany("INSERT INTO ceps VALUES (?)", [(c,) for c in ceps])
    por_cep = defaultdict(list)  # cep -> [(num:int|None, lat, lon)]
    q = """SELECT e.cep, e.num_endereco, e.lat, e.lon
             FROM cnefe.enderecos e JOIN ceps USING (cep)
            WHERE e.lat IS NOT NULL"""
    for cep, nums, la, lo in con.execute(q).fetchall():
        if valid(la, lo):
            n = None
            if nums:
                m = re.findall(r"(\d+)", nums)
                n = int(m[0]) if m else None
            por_cep[cep].append((n, la, lo))
    print(f"CEPs com endereco no CNEFE: {len(por_cep)}")

    # geocodifica cada local faltante
    metodos = defaultdict(int)
    for r in faltam:
        cep = cep8(r["nr_cep"])
        cand = por_cep.get(cep, [])
        if not cand:
            metodos["sem_match"] += 1
            continue
        alvo = num_de(r["ds_endereco"])
        exatos = [(la, lo) for n, la, lo in cand if n is not None and n == alvo]
        if exatos:
            la = sum(x[0] for x in exatos) / len(exatos)
            lo = sum(x[1] for x in exatos) / len(exatos)
            r["lat"], r["lon"], r["fonte_geo"] = round(la, 6), round(lo, 6), "CNEFE_cep_num"
            metodos["cep_num"] += 1
        elif alvo is not None and any(n is not None for n, _, _ in cand):
            n, la, lo = min((c for c in cand if c[0] is not None), key=lambda c: abs(c[0] - alvo))
            r["lat"], r["lon"], r["fonte_geo"] = round(la, 6), round(lo, 6), "CNEFE_cep_prox"
            metodos["cep_prox"] += 1
        else:
            la = median([c[1] for c in cand]); lo = median([c[2] for c in cand])
            r["lat"], r["lon"], r["fonte_geo"] = round(la, 6), round(lo, 6), "CNEFE_cep_centro"
            metodos["cep_centro"] += 1

    # --- fallback final: centroide do municipio (CNEFE) p/ quem sobrou sem CEP ---
    resta = [r for r in faltam if not r["lat"]]
    if resta:
        tse2ibge = {r0[0]: r0[1] for r0 in duckdb.connect(str(DB), read_only=True).execute(
            "SELECT cd_municipio_tse, TRY_CAST(cd_municipio_ibge AS INTEGER) FROM dim_municipio WHERE sg_uf='SP'").fetchall()}
        ibge_need = {tse2ibge.get(r["cd_municipio_tse"]) for r in resta} - {None}
        con.execute("CREATE TEMP TABLE ib(ibge INTEGER)")
        con.executemany("INSERT INTO ib VALUES (?)", [(i,) for i in ibge_need])
        cent = {}
        for cod, la, lo in con.execute("""
            SELECT e.codigo_ibge, median(e.lat), median(e.lon)
              FROM cnefe.enderecos e JOIN ib ON ib.ibge=e.codigo_ibge
             WHERE e.lat IS NOT NULL GROUP BY 1""").fetchall():
            cent[cod] = (la, lo)
        for r in resta:
            c = cent.get(tse2ibge.get(r["cd_municipio_tse"]))
            if c and valid(*c):
                r["lat"], r["lon"], r["fonte_geo"] = round(c[0], 6), round(c[1], 6), "CNEFE_municipio"
                metodos["municipio"] += 1

    for r in rows:
        r.setdefault("fonte_geo", "TSE" if r["lat"] else "")

    print("metodos:", dict(metodos))
    resolvidos = sum(1 for r in faltam if r["lat"])
    print(f"geocodificados: {resolvidos}/{len(faltam)}  (restam {len(faltam)-resolvidos} sem geo)")

    # SAIDA 1: locais enriquecidos
    cols = ["cd_municipio_tse", "nm_municipio", "nr_zona", "nr_local_votacao",
            "nm_local_votacao", "ds_endereco", "nm_bairro", "nr_cep", "lat", "lon", "fonte_geo"]
    out1 = ANALISE / f"locais_por_zona_sp_{ano}_geo.csv"
    with out1.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";", extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"OK: {out1}")

    # SAIDA 2: resumo por zona (recomputa centroide com geo cheio)
    agg = defaultdict(lambda: {"loc": 0, "geo": 0, "lat": [], "lon": [],
                               "bairros": set(), "mun": defaultdict(int)})
    for r in rows:
        a = agg[int(r["nr_zona"])]
        a["loc"] += 1; a["mun"][r["nm_municipio"]] += 1
        if r["lat"]:
            a["geo"] += 1; a["lat"].append(float(r["lat"])); a["lon"].append(float(r["lon"]))
        if r["nm_bairro"]:
            a["bairros"].add(r["nm_bairro"])
    out2 = ANALISE / f"zonas_sp_{ano}_resumo.csv"
    with out2.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["nr_zona", "municipio_sede", "qt_municipios", "municipios",
                    "qt_locais", "qt_locais_geo", "centro_lat", "centro_lon", "qt_bairros"])
        for zona in sorted(agg):
            a = agg[zona]
            clat = round(sum(a["lat"]) / len(a["lat"]), 6) if a["lat"] else ""
            clon = round(sum(a["lon"]) / len(a["lon"]), 6) if a["lon"] else ""
            sede = max(a["mun"].items(), key=lambda kv: kv[1])[0]
            w.writerow([zona, sede, len(a["mun"]), " | ".join(sorted(a["mun"])),
                        a["loc"], a["geo"], clat, clon, len(a["bairros"])])
    sem = sum(1 for z in agg.values() if not z["lat"])
    print(f"OK: {out2}  ({len(agg)} zonas; sem centroide: {sem})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
