#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_enderecos_locais.py
FUNCAO    : UNPIVOT dos enderecos: 1 linha por LOCAL de votacao (nao por zona),
            com rua e numero SEPARADOS, bairro e CEP em colunas proprias, coord,
            e as % de direita/esquerda da zona nos 2 cargos (dep/pres).
            Arquivo dedicado (nome proprio) p/ nao conflitar com ranking_zonas
            aberto no Excel.
FONTES    : data/analise/locais_por_zona_sp_{ano}_geo.csv (1 linha por local)
            data/analise/ranking_zonas_depfederal_{ano}_1t.csv
            data/analise/ranking_zonas_presidente_{ano}_2t.csv
SAIDAS    : data/analise/enderecos_locais_zona_sp_{ano}.csv  (UTF-8 BOM)
            data/analise/enderecos_locais_zona_sp_{ano}.xlsx
USO       : python _scripts/gerar_enderecos_locais.py [ano]   (default 2022)
"""
import csv
import re
import sys
from pathlib import Path

ANALISE = Path(r"D:/Dados_TSE/data/analise")


def split_endereco(end):
    end = (end or "").strip()
    m = re.match(r"^(.*?)[,\s]+(\d+[A-Za-z]?)\s*$", end)
    if m:
        return m.group(1).strip().rstrip(","), m.group(2)
    return end.rstrip(","), ""


def classificar_local(nome):
    """Classifica o local de votacao pelo nome (heuristica)."""
    n = " " + (nome or "").upper() + " "
    if re.search(r"UNIVERSID|FACULDAD|FATEC|\bPUC\b|MACKENZI|\bUNIP\b|UNINOVE|UNESP|\bUSP\b|CENTRO UNIVERSIT|FACULDADES", n):
        return "Universidade"
    if re.search(r"PENITENCI|PRES[IÍ]DIO|CADEIA|\bCDP\b|CENTRO DE DETEN|DETEN[CÇ]|FUNDA[CÇ][AÃ]O CASA", n):
        return "Presidio/Socioeducativo"
    if re.search(r"C[ÂA]MARA|PREFEITURA|SUBPREF|\bF[OÓ]RUM\b|CART[OÓ]RIO|PA[CÇ]O MUNICIPAL", n):
        return "Orgao publico"
    if re.search(r"IGREJA|PAR[OÓ]QUIA|PAROQUIAL|CENTRO COMUNIT|ASSOCIA[CÇ]|SOCIEDADE|\bCLUBE\b|SAL[AÃ]O", n):
        return "Comunitario/Religioso"
    if re.search(r"\bE\.?E\.?\b|\bE\.?M\.?\b|EMEF|EMEI|EMEB|CEMEI|ESCOLA|COL[ÉE]GIO|\bCEU\b|ETEC?|SENAI|SESI|"
                 r"CIEJA|CIEP|CENTRO EDUC|CENTRO DE ENSINO|INST.*EDUC|\bEDUC", n):
        return "Escola"
    return "Outros"


def ler_ranking(nome):
    p = ANALISE / nome
    d = {}
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8-sig"), delimiter=";"):
            d[int(r["nr_zona"])] = r
    return d


def main():
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    src = ANALISE / f"locais_por_zona_sp_{ano}_geo.csv"
    if not src.exists():
        src = ANALISE / f"locais_por_zona_sp_{ano}.csv"
    dep = ler_ranking(f"ranking_zonas_depfederal_{ano}_1t.csv")
    pres = ler_ranking(f"ranking_zonas_presidente_{ano}_2t.csv")

    cols = ["nr_zona", "cd_municipio_tse", "nm_municipio", "nr_local_votacao",
            "nm_local_votacao", "tipo_local", "logradouro", "numero", "nm_bairro", "nr_cep",
            "ds_endereco", "lat", "lon", "fonte_geo",
            "dep_pct_dir", "dep_pct_esq", "dep_vencedor",
            "pres_pct_dir", "pres_pct_esq", "pres_vencedor"]

    linhas = []
    for r in csv.DictReader(src.open(encoding="utf-8-sig"), delimiter=";"):
        z = int(r["nr_zona"]); dd = dep.get(z, {}); pp = pres.get(z, {})
        logr, num = split_endereco(r.get("ds_endereco", ""))
        linhas.append({
            "nr_zona": z, "cd_municipio_tse": r.get("cd_municipio_tse", ""),
            "nm_municipio": r.get("nm_municipio", ""),
            "nr_local_votacao": int(r["nr_local_votacao"]),
            "nm_local_votacao": r.get("nm_local_votacao", ""),
            "tipo_local": classificar_local(r.get("nm_local_votacao", "")),
            "logradouro": logr, "numero": num,
            "nm_bairro": r.get("nm_bairro", ""), "nr_cep": r.get("nr_cep", ""),
            "ds_endereco": r.get("ds_endereco", ""),
            "lat": r.get("lat", ""), "lon": r.get("lon", ""),
            "fonte_geo": r.get("fonte_geo", ""),
            "dep_pct_dir": dd.get("pct_dir", ""), "dep_pct_esq": dd.get("pct_esq", ""),
            "dep_vencedor": dd.get("vencedor", ""),
            "pres_pct_dir": pp.get("pct_dir", ""), "pres_pct_esq": pp.get("pct_esq", ""),
            "pres_vencedor": pp.get("vencedor", ""),
        })
    linhas.sort(key=lambda d: (d["nr_zona"], d["nr_local_votacao"]))

    out_csv = ANALISE / f"enderecos_locais_zona_sp_{ano}.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader(); w.writerows(linhas)
    print(f"OK: {out_csv.name}  ({len(linhas):,} locais, 1 por linha)")

    try:
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "Enderecos_locais"
        ws.append(cols)
        for d in linhas:
            ws.append([d[c] for c in cols])
        ws.freeze_panes = "A2"
        out_xlsx = ANALISE / f"enderecos_locais_zona_sp_{ano}.xlsx"
        wb.save(out_xlsx)
        print(f"OK: {out_xlsx.name}")
    except ImportError:
        print("(openpyxl indisponivel; XLSX pulado)")
    except PermissionError:
        print("XLSX travado (aberto no Excel?); CSV foi gravado normalmente.")

    def a(s): return str(s).encode("ascii", "replace").decode()
    print("\n=== amostra (rua/numero separados) ===")
    for d in linhas[:4]:
        print(f"  z{d['nr_zona']} {a(d['nm_municipio'])} | RUA='{a(d['logradouro'])}' "
              f"Nº='{d['numero']}' BAIRRO='{a(d['nm_bairro'])}' CEP={d['nr_cep']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
