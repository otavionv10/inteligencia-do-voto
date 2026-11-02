#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_locais_por_zona.py
FUNCAO    : Reconstroi os LOCAIS DE VOTACAO de SP com a chave correta
            (municipio, zona, local) a partir da fonte crua
            eleitorado_local_votacao_{ano}, preservando endereco, bairro, CEP e
            lat/lon. A dim_local_votacao do banco perde nr_zona (chave so
            municipio+local) e subconta ~30% dos locais; aqui corrigimos.
            Uma ZONA ELEITORAL e identificada por nr_zona (unica no estado, 393
            em SP) e pode abranger varios municipios; por isso o resumo por zona
            e agregado por nr_zona (SP inteiro).
            Coordenadas invalidas (placeholder -1,-1 ou fora do bbox de SP) sao
            tratadas como ausentes e nao entram no centroide.
FONTE     : data/extracted/local_votacao/{ano}/eleitorado_local_votacao_{ano}.csv
            (arquivo BRASIL; filtramos SG_UF='SP'). CSV latin-1, delim ';',
            coordenada com virgula decimal.
SAIDAS    : data/analise/locais_por_zona_sp_{ano}.csv   (1 linha por local)
            data/analise/zonas_sp_{ano}_resumo.csv       (1 linha por nr_zona)
USO       : python _scripts/gerar_locais_por_zona.py [ano]   (default 2022)
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(r"D:/Dados_TSE")
ANALISE = BASE / "data" / "analise"

# Bounding box aproximado do estado de SP (lat, lon)
SP_LAT = (-25.6, -19.4)
SP_LON = (-53.6, -44.0)


def coord_pair(slat, slon):
    """Retorna (lat, lon) validos dentro do bbox de SP, ou (None, None)."""
    def num(v):
        v = (v or "").strip().replace(",", ".")
        try:
            return float(v)
        except ValueError:
            return None
    la, lo = num(slat), num(slon)
    if la is None or lo is None:
        return None, None
    if not (SP_LAT[0] <= la <= SP_LAT[1] and SP_LON[0] <= lo <= SP_LON[1]):
        return None, None
    return la, lo


def raw_path(ano):
    d = BASE / "data" / "extracted" / "local_votacao" / str(ano)
    for name in (f"eleitorado_local_votacao_{ano}.csv",
                 f"eleitorado_local_votacao_{ano}_SP.csv",
                 f"eleitorado_local_votacao_{ano}_BRASIL.csv"):
        if (d / name).exists():
            return d / name
    raise FileNotFoundError(f"fonte crua nao encontrada para {ano} em {d}")


def main():
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    src = raw_path(ano)
    print(f"Fonte: {src}")

    # 1 registro por (municipio, zona, local); guarda o 1o registro visto
    locais = {}
    # OBS: eleitorado_local_votacao e UTF-8 (nao latin-1 como outros CSVs do TSE);
    # errors=replace cobre bytes ruins raros.
    with src.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        r = csv.DictReader(f, delimiter=";")
        for row in r:
            if row.get("SG_UF") != "SP":
                continue
            k = (row["CD_MUNICIPIO"], row["NR_ZONA"], row["NR_LOCAL_VOTACAO"])
            if k in locais:
                continue
            la, lo = coord_pair(row.get("NR_LATITUDE"), row.get("NR_LONGITUDE"))
            locais[k] = {
                "cd_municipio_tse": row["CD_MUNICIPIO"],
                "nm_municipio": (row.get("NM_MUNICIPIO") or "").strip(),
                "nr_zona": int(row["NR_ZONA"]),
                "nr_local_votacao": int(row["NR_LOCAL_VOTACAO"]),
                "nm_local_votacao": (row.get("NM_LOCAL_VOTACAO") or "").strip(),
                "ds_endereco": (row.get("DS_ENDERECO") or "").strip(),
                "nm_bairro": (row.get("NM_BAIRRO") or "").strip(),
                "nr_cep": (row.get("NR_CEP") or "").strip(),
                "lat": la, "lon": lo,
            }

    rows = sorted(locais.values(),
                  key=lambda d: (d["nm_municipio"], d["nr_zona"], d["nr_local_votacao"]))
    com_geo = sum(1 for d in rows if d["lat"] is not None)
    zonas_uf = {d["nr_zona"] for d in rows}
    print(f"SP {ano}: {len(rows):,} locais (municipio,zona,local) | {com_geo:,} com lat/lon valida "
          f"| {len(rows)-com_geo:,} sem geo | {len(zonas_uf):,} zonas eleitorais "
          f"| {len({(d['cd_municipio_tse'], d['nr_zona']) for d in rows}):,} pares municipio-zona")

    # SAIDA 1: locais por zona (endereco de cada local)
    out1 = ANALISE / f"locais_por_zona_sp_{ano}.csv"
    cols = ["cd_municipio_tse", "nm_municipio", "nr_zona", "nr_local_votacao",
            "nm_local_votacao", "ds_endereco", "nm_bairro", "nr_cep", "lat", "lon"]
    with out1.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        for d in rows:
            w.writerow({**d, "lat": "" if d["lat"] is None else d["lat"],
                        "lon": "" if d["lon"] is None else d["lon"]})
    print(f"OK: {out1}")

    # SAIDA 2: resumo por ZONA ELEITORAL (nr_zona, SP inteiro) com centroide
    agg = defaultdict(lambda: {"locais": 0, "geo": 0, "lat": [], "lon": [],
                               "bairros": set(), "mun": defaultdict(int)})
    for d in rows:
        a = agg[d["nr_zona"]]
        a["locais"] += 1
        a["mun"][d["nm_municipio"]] += 1
        if d["lat"] is not None:
            a["geo"] += 1; a["lat"].append(d["lat"]); a["lon"].append(d["lon"])
        if d["nm_bairro"]:
            a["bairros"].add(d["nm_bairro"])
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
                        a["locais"], a["geo"], clat, clon, len(a["bairros"])])
    print(f"OK: {out2}  ({len(agg):,} zonas eleitorais)")

    def asc(s): return (s or "").encode("ascii", "replace").decode("ascii")
    print("\n=== amostra: primeiras zonas (resumo) ===")
    for zona in sorted(agg)[:4]:
        a = agg[zona]
        sede = max(a["mun"].items(), key=lambda kv: kv[1])[0]
        print(f"  zona {zona}: {a['locais']} locais ({a['geo']} c/geo) | "
              f"{len(a['mun'])} municipios (sede {asc(sede)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
