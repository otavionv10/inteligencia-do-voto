#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/enrich_ibge_brasil.py
FUNCAO    : Enriquecer dim_municipio (brasil.duckdb) com indicadores IBGE
            - Censo 2022: populacao, area (km2), densidade  -> SIDRA 4714
            - PIB 2023 (R$ mil)                              -> SIDRA 5938 (var 37)
              (per capita = PIB*1000 / pop censo 2022)
            - IDHM 2010 nacional (Atlas PNUD, todos municipios) -> download
              do arquivo oficial do Atlas (idhm_atlas2013.xlsx / .csv)
FONTE     : https://apisidra.ibge.gov.br ; http://www.atlasbrasil.org.br
USO       : python _scripts/enrich_ibge_brasil.py [--no-idh] [--dir data/ibge]
SAIDAS    : IBGE_DIR/ibge_indicadores_brasil.csv + colunas no dim_municipio
Criado    : 2026-09-28
=============================================================================
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import duckdb

ANA = Path(__file__).resolve()
ROOT = ANA.parent.parent
DB_BR = ROOT / "data" / "db" / "brasil.duckdb"
IBGE_DIR = ROOT / "data" / "ibge"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}


def get_json(url, timeout=240):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def sidra_municipal(tabela, variaveis, periodo):
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
        return float(v.replace(",", "."))
    except ValueError:
        return None


def fetch_idh_br(dest):
    """IDHM 2010 nacional (5.565 municipios) via CSV do Atlas Brasil (PNUD/Ipea/FJP)."""
    dest.mkdir(parents=True, exist_ok=True)
    url = "https://raw.githubusercontent.com/miromachado/nasa-hackathon/master/dados2010.csv"
    csv_path = dest / "idhm_2010_atlas_br.csv"
    if not csv_path.exists():
        print(f"  baixando {url}")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r:
            csv_path.write_bytes(r.read().decode("utf-8", "replace").encode("utf-8"))
    import csv
    out = {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = (row.get("cod7") or "").strip()
            if not code:
                continue
            out[code] = {
                "idhm_2010": row.get("idhm"),
                "idhm_educacao_2010": row.get("idhm_edu"),
                "idhm_longevidade_2010": row.get("idhm_longev"),
                "idhm_renda_2010": row.get("idhm_renda"),
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-idh", action="store_true", help="pula IDHM (atlas)")
    args = ap.parse_args()
    IBGE_DIR.mkdir(parents=True, exist_ok=True)

    print("Fase 1: Censo 2022 (pop, area, densidade) via SIDRA..")
    censo = sidra_municipal("4714", "93,6318,614", "2022")
    print(f"  municipios com dados: {len(censo)}")

    print("Fase 2: PIB 2023 (total, R$ mil) via SIDRA..")
    pib = sidra_municipal("5938", "37", "2023")
    print(f"  municipios com dados: {len(pib)}")

    idh = None
    if not args.no_idh:
        print("Fase 3: IDHM 2010 (Atlas Brasil, nacional)..")
        idh = fetch_idh_br(IBGE_DIR / "idh")
        print(f"  municipios com IDHM: {len(idh)}")
        idhm_ix = {code: v for code, v in idh.items()}
    else:
        print("Fase 3: pulada (--no-idh)")
        idhm_ix = {}

    path_out = IBGE_DIR / "ibge_indicadores_brasil.csv"
    with open(path_out, "w", encoding="utf-8") as f:
        f.write("cod_ibge;pop_2022;area_km2;dens_2022;pib_2023_mil;pib_pc_2023;"
                "idhm_2010;idhm_educacao_2010;idhm_longevidade_2010;idhm_renda_2010\n")
        for code, cd in censo.items():
            pop = val_float(cd, "93")
            area = val_float(cd, "6318")
            dens = val_float(cd, "614")
            pib_mil = val_float(pib.get(code, {}), "37")
            pib_pc = (pib_mil * 1000.0 / pop) if (pib_mil and pop) else None
            ih = idhm_ix.get(code)
            f.write(";".join(
                "" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))
                for x in (code, pop, area, dens, pib_mil, pib_pc,
                          None if ih is None else ih.get("idhm_2010"),
                          None if ih is None else ih.get("idhm_educacao_2010"),
                          None if ih is None else ih.get("idhm_longevidade_2010"),
                          None if ih is None else ih.get("idhm_renda_2010"))
            ) + "\n")
    print(f"  snapshot salvo: {path_out}")

    print("Fase 4: alterar dim_municipio e popular..")
    con = duckdb.connect(str(DB_BR))
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
    con.execute(f"""CREATE OR REPLACE TEMP TABLE ibge_ext AS
        SELECT * FROM read_csv_auto('{path_out}', header=true, delim=';',
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
    """)
    print("  dim_municipio atualizado.")

    print("\n-- validacao nacional --")
    for r in con.execute("""
        SELECT COUNT(*) AS mun, COUNT(ibge_pop_2022) AS c_pop,
               COUNT(ibge_pib_2023_mil) AS c_pib,
               COUNT(ibge_idhm_2010) AS c_idh,
               ROUND(SUM(ibge_pop_2022)) AS pop_total,
               ROUND(AVG(ibge_idhm_2010), 4) AS idhm_medio
        FROM dim_municipio
    """).fetchall():
        print("  ", r)
    print("-- amostra --")
    for r in con.execute("""
        SELECT sg_uf, nm_municipio_tse, ibge_pop_2022, ibge_area_km2, ibge_dens_2022,
               ibge_pib_2023_mil, ibge_pib_pc_2023, ibge_idhm_2010
        FROM dim_municipio WHERE cd_municipio_ibge IN ('3550308','3304557','5300108','1200401')
    """).fetchall():
        print("  ", r)
    con.close()


if __name__ == "__main__":
    sys.exit(main())