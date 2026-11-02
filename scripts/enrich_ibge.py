"""
=============================================================================
ARQUIVO   : _scripts/enrich_ibge.py
FUNCAO    : Enriquecer dim_municipio com indicadores IBGE por municipio
            - Censo 2022: populacao, area (km2), densidade  -> SIDRA tabela 4714
            - PIB 2023 (R$ mil)                              -> SIDRA tabela 5938 (var 37)
              (per capita = PIB * 1000 / pop censo 2022, metodologia IBGE)
            - IDHM 2010 (geral, educacao, longevidade, renda) -> SEADE/Atlas PNUD (SP)
FONTE     : https://apisidra.ibge.gov.br/ ; https://repositorio.seade.gov.br
USO       : python _scripts/enrich_ibge.py [--no-idh]
CRIADO    : 2026-09-20
=============================================================================
"""
import argparse
import json
import struct
import sys
import urllib.request
import zipfile
from io import BytesIO

from common import DB_PATH, IBGE_DIR, ensure_dirs
import duckdb

IDH_ZIP_URL = ("https://repositorio.seade.gov.br/dataset/2be01068-49cc-4cc1-85b8-38bd867aefc4/"
               "resource/fe872142-e28d-49bd-9b45-9287608b5c92/download/idhm.zip")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}


def get_json(url, timeout=180):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def sidra_municipal(tabela, variaveis, periodo):
    """Retorna {cod_ibge7: {var_id: valor_str}} para todo municipio (n6/all)."""
    url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/n6/all/v/{variaveis}/p/{periodo}"
    j = get_json(url)
    out = {}
    for row in j[1:]:
        code = row.get("D1C") or ""
        var = row.get("D2C") or ""
        val = (row.get("V") or "").strip()
        if code and var:
            out.setdefault(code, {})[var] = val
    return out


def val_float(d, var):
    v = d.get(var)
    if v is None or v == "" or v == "...":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_dbf(zip_bytes, member):
    data = zipfile.ZipFile(BytesIO(zip_bytes)).read(member)
    rec_count = struct.unpack("<I", data[4:8])[0]
    hdr_len = struct.unpack("<H", data[8:10])[0]
    fields = []
    pos = 32
    while data[pos:pos + 32] and data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\x00")[0].decode("latin-1")
        ftype = chr(data[pos + 11])
        fields.append((name, ftype, data[pos + 16]))
        pos += 32
    rec_start = pos + 1
    rec_len = sum(f[2] for f in fields) + 1
    rows = []
    for i in range(rec_count):
        rec = data[rec_start + i * rec_len: rec_start + (i + 1) * rec_len]
        if len(rec) < rec_len:
            continue
        vals = {}
        off = 1
        for name, ftype, length in fields:
            vals[name] = rec[off:off + length].decode("latin-1").strip()
            off += length
        rows.append(vals)
    return rows


def fetch_idh(tmp_dir):
    """Baixa e parseia o shapefile de IDHM 2010 (SP 645 municipios)."""
    import shutil
    from curl_cffi import requests as cr
    url_parts = IDH_ZIP_URL.split("/")
    url = url_parts[0] + "//" + url_parts[2] + "/" + "/".join(url_parts[3:])
    r = cr.get(url, impersonate="chrome124", timeout=300)
    r.raise_for_status()
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "idhm.zip").write_bytes(r.content)
    return parse_dbf(r.content, "IDHM.dbf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-idh", action="store_true", help="pula IDHM (atlas)")
    args = ap.parse_args()

    ensure_dirs()
    cin = duckdb.connect(str(DB_PATH))
    cin.close()

    print("Fase 1: Censo 2022 (pop, area, densidade) via SIDRA..")
    censo = sidra_municipal("4714", "93,6318,614", "2022")
    print(f"  municipios com dados: {len(censo)}")

    print("Fase 2: PIB 2023 (total, R$ mil) via SIDRA..")
    pib = sidra_municipal("5938", "37", "2023")
    print(f"  municipios com dados: {len(pib)}")

    idh_rows = []
    if not args.no_idh:
        print("Fase 3: IDHM 2010 (Atlas PNUD/SEADE, shapefile SP)..")
        idh_rows = fetch_idh(IBGE_DIR / "idh")
        print(f"  municipios com IDHM: {len(idh_rows)}")
    else:
        print("Fase 3: pulada (--no-idh)")

    # monta mapa cod_ibge -> indicadores
    path_out = IBGE_DIR / "ibge_indicadores.csv"
    with open(path_out, "w", encoding="utf-8") as f:
        f.write("cod_ibge;pop_2022;area_km2;dens_2022;pib_2023_mil;pib_pc_2023;"
                "idhm_2010;idhm_educacao_2010;idhm_longevidade_2010;idhm_renda_2010\n")
        for code, cd in censo.items():
            pop = val_float(cd, "93")
            area = val_float(cd, "6318")
            dens = val_float(cd, "614")
            pib_mil = val_float(pib.get(code, {}), "37")
            pib_pc = (pib_mil * 1000.0 / pop) if (pib_mil and pop) else None
            idh = next((r for r in idh_rows if r.get("Cod_ibge") == code), None)
            f.write(";".join(
                "" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))
                for x in (code, pop, area, dens, pib_mil, pib_pc,
                          val_float(idh, "IDMH") if idh else None,
                          val_float(idh, "IDHM_E") if idh else None,
                          val_float(idh, "IDHM_L") if idh else None,
                          val_float(idh, "IDHM_R") if idh else None)
            ) + "\n")
    print(f"  snapshot salvo: {path_out}")

    print("Fase 4: alterar dim_municipio e popular..")
    con = duckdb.connect(str(DB_PATH))
    cols = {
        "ibge_pop_2022": "BIGINT",
        "ibge_area_km2": "DOUBLE",
        "ibge_dens_2022": "DOUBLE",
        "ibge_pib_2023_mil": "BIGINT",
        "ibge_pib_pc_2023": "DOUBLE",
        "ibge_idhm_2010": "DOUBLE",
        "ibge_idhm_educacao_2010": "DOUBLE",
        "ibge_idhm_longevidade_2010": "DOUBLE",
        "ibge_idhm_renda_2010": "DOUBLE",
    }
    for col, t in cols.items():
        if col not in [r[0] for r in con.execute("DESCRIBE dim_municipio").fetchall()]:
            con.execute(f"ALTER TABLE dim_municipio ADD COLUMN {col} {t}")
    con.execute("""CREATE OR REPLACE TEMP TABLE ibge_ext AS
        SELECT * FROM read_csv_auto('""" + str(path_out) + """', header=true, delim=';',
                   all_varchar=true, sample_size=-1)""")
    con.execute("""
        UPDATE dim_municipio m SET
            ibge_pop_2022     = TRY_CAST(x.pop_2022 AS BIGINT),
            ibge_area_km2     = TRY_CAST(x.area_km2 AS DOUBLE),
            ibge_dens_2022    = TRY_CAST(x.dens_2022 AS DOUBLE),
            ibge_pib_2023_mil = TRY_CAST(x.pib_2023_mil AS BIGINT),
            ibge_pib_pc_2023  = TRY_CAST(REPLACE(x.pib_pc_2023,',','.') AS DOUBLE),
            ibge_idhm_2010    = TRY_CAST(REPLACE(x.idhm_2010,',','.') AS DOUBLE),
            ibge_idhm_educacao_2010 = TRY_CAST(REPLACE(x.idhm_educacao_2010,',','.') AS DOUBLE),
            ibge_idhm_longevidade_2010 = TRY_CAST(REPLACE(x.idhm_longevidade_2010,',','.') AS DOUBLE),
            ibge_idhm_renda_2010 = TRY_CAST(REPLACE(x.idhm_renda_2010,',','.') AS DOUBLE)
        FROM ibge_ext x WHERE m.cd_municipio_ibge = LPAD(x.cod_ibge, 7, '0')
    """, )
    print("  dim_municipio atualizado.")

    print("\n-- validacao (SP) --")
    for r in con.execute("""
        SELECT 'SP',
               COUNT(*)                             AS mun,
               COUNT(ibge_pop_2022)                 AS c_pop,
               COUNT(ibge_pib_2023_mil)             AS c_pib,
               COUNT(ibge_idhm_2010)                AS c_idh,
               ROUND(SUM(ibge_pop_2022))            AS pop_total,
               ROUND(AVG(ibge_idhm_2010), 3)        AS idhm_medio
        FROM dim_municipio WHERE sg_uf = 'SP'
    """).fetchall():
        print("  ", r)
    print("-- amostra SP cidade --")
    for r in con.execute("""
        SELECT nm_municipio_tse, ibge_pop_2022, ibge_area_km2, ibge_dens_2022,
               ibge_pib_2023_mil, ibge_pib_pc_2023, ibge_idhm_2010
        FROM dim_municipio WHERE cd_municipio_ibge IN ('3550308','3549904','3509502')
    """).fetchall():
        print("  ", r)
    con.close()


if __name__ == "__main__":
    sys.exit(main())