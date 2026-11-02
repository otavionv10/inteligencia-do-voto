# -*- coding: utf-8 -*-
"""Baixa malha municipal 2025 do IBGE por UF e converte p/ GeoJSON por estado.
   USO: python _scripts/baixar_malha_uf.py [UF UF ...]   (sem arg = todos)
   Saida: data/geo/uf/{UF}_municipios.geojson (cod IBGE 7 dig, SIRGAS->WGS84 simplificado)
"""
import sys
import zipfile
import urllib.request
from pathlib import Path

import duckdb

BASE = ("https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
        "malhas_municipais/municipio_2025/UFs")
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "geo" / "uf"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP = Path(__file__).resolve().parent.parent / "data" / "geo" / "_tmp_uf_2025"

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG",
       "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR",
       "RS", "SC", "SE", "SP", "TO"]


def download(url, dest):
    print(f"  baixando {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)


def convert_uf(uf):
    zpath = TMP / f"{uf}_Municipios_2025.zip"
    if not zpath.exists():
        download(f"{BASE}/{uf}/{uf}_Municipios_2025.zip", zpath)

    extract = TMP / f"{uf}"
    extract.mkdir(exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            out = extract / Path(n).name
            if not out.exists():
                with z.open(n) as src, open(out, "wb") as dst:
                    dst.write(src.read())

    shp = next(extract.glob("*.shp"), None)
    if shp is None:
        print(f"  ! {uf}: sem .shp no zip")
        return
    out = OUT_DIR / f"{uf}_municipios.geojson"
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"""
        CREATE TABLE m AS
        SELECT CD_MUN AS cd_municipio_ibge,
               NM_MUN AS nm_municipio,
               CD_UF  AS cd_uf,
               NM_UF  AS nm_uf,
               ST_Transform(geom, 'EPSG:4326') AS geom
        FROM ST_Read('{shp}')
    """)
    n = con.execute("SELECT COUNT(*) FROM m").fetchone()[0]
    con.execute(f"""
        COPY (SELECT cd_municipio_ibge, nm_municipio, cd_uf,
                     ST_SimplifyPreserveTopology(geom, 0.001) AS geom
              FROM m)
        TO '{out}' (FORMAT GDAL, DRIVER 'GeoJSON')
    """)
    con.close()
    print(f"  ok {uf}: {n} municipios -> {out.name} ({out.stat().st_size/1e6:.2f} MB)")


def main():
    ufs = [u.upper() for u in sys.argv[1:]] or UFS
    TMP.mkdir(exist_ok=True)
    for uf in ufs:
        convert_uf(uf)


if __name__ == "__main__":
    sys.exit(main())