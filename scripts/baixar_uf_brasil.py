# -*- coding: utf-8 -*-
"""Baixa limite das UFs do Brasil (IBGE malha 2025) e converte p/ GeoJSON.
   USO: python _scripts/baixar_uf_brasil.py
   Saida: data/geo/br_uf.geojson (27 UFs, cod IBGE 2 dig, WGS84 simplificado)
"""
import sys
import zipfile
import urllib.request
from pathlib import Path

import duckdb

URL = ("https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
       "malhas_municipais/municipio_2025/Brasil/BR_UF_2025.zip")
GEO_DIR = Path(__file__).resolve().parent.parent / "data" / "geo"
OUT = GEO_DIR / "br_uf.geojson"
ZIP = GEO_DIR / "br_uf_2025.zip"
TMP = GEO_DIR / "_tmp_br_uf_2025"


def download(url, dest):
    print(f"baixando {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)


def main():
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    if not ZIP.exists():
        download(URL, ZIP)

    TMP.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP) as z:
        for n in z.namelist():
            out = TMP / Path(n).name
            with z.open(n) as src, open(out, "wb") as dst:
                dst.write(src.read())

    shp = next(TMP.glob("*.shp"), None)
    if shp is None:
        print("sem .shp no zip")
        return 1
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    cols = con.execute(f"SELECT * FROM ST_Read('{shp}') LIMIT 1").description
    print("colunas shape:", [c[0] for c in cols])
    n = con.execute(f"SELECT count(*) FROM ST_Read('{shp}')").fetchone()[0]
    print("UFs no shape:", n)
    con.execute(f"""
        COPY (SELECT CD_UF AS cd_uf, SIGLA_UF AS sg_uf, NM_UF AS nm_uf,
                     ST_SimplifyPreserveTopology(ST_Transform(geom, 'EPSG:4326'), 0.001) AS geom
              FROM ST_Read('{shp}'))
        TO '{OUT}' (FORMAT GDAL, DRIVER 'GeoJSON')
    """)
    con.close()
    print(f"geojson: {OUT} ({OUT.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    sys.exit(main())