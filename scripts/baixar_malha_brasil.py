# -*- coding: utf-8 -*-
"""Baixa malha municipal completa do Brasil (IBGE geoftp) e converte p/ GeoJSON.
   USO: python _scripts/baixar_malha_brasil.py
   Saida: data/geo/br_municipios.geojson (5.571 municipios, cod IBGE 7 dig)
"""
import io
import sys
import zipfile
import urllib.request
from pathlib import Path

import duckdb

URL = ("https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
       "malhas_municipais/municipio_2023/Brasil/BR_Municipios_2023.zip")
OUT = Path(__file__).resolve().parent.parent / "data" / "geo" / "br_municipios.geojson"
OUT.parent.mkdir(parents=True, exist_ok=True)
TMP_SHPS = OUT.parent / "_tmp_shp_br_2023"
TMP_GPKG = OUT.parent / "_tmp_br_municipios.gpkg"


def download(url, dest):
    print(f"baixando {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    print(f"  ok: {dest} ({dest.stat().st_size/1e6:.1f} MB)")


def main():
    zpath = OUT.parent / "br_municipios_2023.zip"
    if not zpath.exists():
        download(URL, zpath)

    # lista membros
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
    shps = [n for n in names if n.lower().endswith(".shp")]
    if not shps:
        print("sem .shp no zip:", names[:10])
        return 1

    TMP_SHPS.mkdir(exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        for n in names:
            out = TMP_SHPS / Path(n).name
            if not out.exists():
                with z.open(n) as src, open(out, "wb") as dst:
                    dst.write(src.read())
    print(f"extraidos {len(list(TMP_SHPS.glob('*')))} arquivos")

    # converte SHP -> GeoJSON via DuckDB spatial
    # SIRGAS 2000 (EPSG:4674) ~= WGS84 (EPSG:4326); transforma e simplifica
    shp = next(TMP_SHPS.glob("*.shp"))
    print(f"convertendo {shp.name} -> geojson (pode demorar)...")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("CREATE TABLE m AS SELECT CD_MUN AS cd_municipio_ibge, NM_MUN AS nm_municipio, "
                "CD_UF AS cd_uf, NM_UF AS nm_uf, ST_Transform(geom, 'EPSG:4326') AS geom "
                f"FROM ST_Read('{shp}')")
    n = con.execute("SELECT COUNT(*) FROM m").fetchone()[0]
    print(f"  municipios no shape: {n}")
    con.execute(f"""
        COPY (SELECT cd_municipio_ibge, nm_municipio, cd_uf, nm_uf,
                     ST_SimplifyPreserveTopology(ST_Transform(geom, 'EPSG:4326'), 0.001) AS geom
              FROM m)
        TO '{OUT}' (FORMAT GDAL, DRIVER 'GeoJSON')
    """)
    con.close()
    print(f"geojson: {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())