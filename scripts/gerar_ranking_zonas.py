#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_ranking_zonas.py
FUNCAO    : Ranking das ZONAS eleitorais de SP por campo politico (DIREITA/
            CENTRO/ESQUERDA), por cargo/ano/turno, cruzado com os ENDERECOS/
            centroide de cada zona (de zonas_sp_{ano}_resumo.csv, gerado por
            gerar_locais_por_zona.py). Responde: "zonas com mais voto de
            direita/esquerda e o endereco delas".
FONTES    : data/db/sao_paulo.duckdb (fact_votacao_secao + vw_candidato_campo)
            data/analise/zonas_sp_{ano}_resumo.csv (centroide + bairros)
SAIDAS    : data/analise/ranking_zonas_{slug}_{ano}_{t}t.csv  (UTF-8 BOM)
            data/analise/ranking_zonas_sp_{ano}.xlsx          (1 aba por cargo)
USO       : python _scripts/gerar_ranking_zonas.py
NOTA      : join por sq_candidato (valido p/ 2018/2022). 2014 exige o mapa por
            nr_votavel (ver ranking_secoes_deputado_federal.py) - fora do escopo.
"""
import csv
import sys
from pathlib import Path

import duckdb

BASE = Path(r"D:/Dados_TSE")
DB = BASE / "data" / "db" / "sao_paulo.duckdb"
ANALISE = BASE / "data" / "analise"

# (rotulo, cargo UPPER, turno, slug)
ALVOS = [
    ("Presidente 2T", "PRESIDENTE", 2, "presidente"),
    ("Deputado Federal 1T", "DEPUTADO FEDERAL", 1, "depfederal"),
]


def split_endereco(end):
    """'AV. PAULISTA, 900' -> ('AV. PAULISTA', '900'). Sem numero -> ('...', '')."""
    import re
    end = (end or "").strip()
    m = re.match(r"^(.*?)[,\s]+(\d+[A-Za-z]?)\s*$", end)
    if m:
        return m.group(1).strip().rstrip(","), m.group(2)
    return end.rstrip(","), ""


def ler_zonas_resumo(ano):
    path = ANALISE / f"zonas_sp_{ano}_resumo.csv"
    z = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            z[int(row["nr_zona"])] = row
    return z


def ler_enderecos_por_zona(ano):
    """zona -> (enderecos dos locais, bairros distintos, CEPs distintos)."""
    from collections import defaultdict
    p = ANALISE / f"locais_por_zona_sp_{ano}_geo.csv"
    if not p.exists():
        p = ANALISE / f"locais_por_zona_sp_{ano}.csv"
    ends = defaultdict(list)
    bairros = defaultdict(list)  # ordem preservada, sem repetir
    ceps = defaultdict(list)
    with p.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            z = int(r["nr_zona"])
            local = r["nm_local_votacao"].strip()
            end = r["ds_endereco"].strip()
            bai = r["nm_bairro"].strip()
            cep = r["nr_cep"].strip()
            txt = f"{local}: {end}" + (f" ({bai})" if bai else "")
            ends[z].append(txt)
            if bai and bai not in bairros[z]:
                bairros[z].append(bai)
            if cep and cep not in ceps[z]:
                ceps[z].append(cep)
    end_map = {z: " | ".join(v) for z, v in ends.items()}
    bai_map = {z: " | ".join(v) for z, v in bairros.items()}
    cep_map = {z: " | ".join(v) for z, v in ceps.items()}
    return end_map, bai_map, cep_map


def votos_por_zona(con, ano, cargo, turno):
    q = f"""
    SELECT v.nr_zona,
           SUM(v.qt_votos) FILTER (WHERE c.campo='ESQUERDA') AS vot_esq,
           SUM(v.qt_votos) FILTER (WHERE c.campo='CENTRO')   AS vot_cen,
           SUM(v.qt_votos) FILTER (WHERE c.campo='DIREITA')  AS vot_dir,
           SUM(v.qt_votos) FILTER (WHERE v.nr_votavel NOT IN (95,96,97)) AS validos
      FROM fact_votacao_secao v
      LEFT JOIN vw_candidato_campo c
             ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
     WHERE v.ano_eletivo={ano} AND UPPER(v.ds_cargo)='{cargo}' AND v.nr_turno={turno}
     GROUP BY 1
    """
    return con.execute(q).fetchall()


def main():
    ano = 2022
    con = duckdb.connect(str(DB), read_only=True)
    zonas = ler_zonas_resumo(ano)
    end_map, bai_map, cep_map = ler_enderecos_por_zona(ano)

    abas = {}  # rotulo -> lista de dicts (p/ xlsx)
    for rotulo, cargo, turno, slug in ALVOS:
        linhas = []
        tot_dir = tot_esq = tot_cen = tot_val = 0
        for zona, esq, cen, dire, val in votos_por_zona(con, ano, cargo, turno):
            esq, cen, dire, val = (esq or 0), (cen or 0), (dire or 0), (val or 0)
            zr = zonas.get(zona, {})
            pdir = round(100.0 * dire / val, 2) if val else 0.0
            pesq = round(100.0 * esq / val, 2) if val else 0.0
            pcen = round(100.0 * cen / val, 2) if val else 0.0
            venc = max((("DIREITA", dire), ("CENTRO", cen), ("ESQUERDA", esq)), key=lambda t: t[1])[0]
            linhas.append({
                "nr_zona": zona,
                "municipio_sede": zr.get("municipio_sede", ""),
                "qt_municipios": zr.get("qt_municipios", ""),
                "municipios": zr.get("municipios", ""),
                "qt_locais": zr.get("qt_locais", ""),
                "vot_esq": esq, "vot_cen": cen, "vot_dir": dire, "validos": val,
                "pct_dir": pdir, "pct_esq": pesq, "pct_cen": pcen,
                "vencedor": venc,
                "centro_lat": zr.get("centro_lat", ""),
                "centro_lon": zr.get("centro_lon", ""),
                "bairros": bai_map.get(zona, ""),
                "ceps": cep_map.get(zona, ""),
                "enderecos_dos_locais": end_map.get(zona, ""),
            })
            tot_dir += dire; tot_esq += esq; tot_cen += cen; tot_val += val
        linhas.sort(key=lambda d: d["pct_dir"], reverse=True)

        cols = ["nr_zona", "municipio_sede", "qt_municipios", "municipios", "qt_locais",
                "vot_esq", "vot_cen", "vot_dir", "validos",
                "pct_dir", "pct_esq", "pct_cen", "vencedor",
                "centro_lat", "centro_lon", "bairros", "ceps", "enderecos_dos_locais"]
        out = ANALISE / f"ranking_zonas_{slug}_{ano}_{turno}t.csv"
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
            w.writeheader(); w.writerows(linhas)
        abas[rotulo] = (cols, linhas)
        pd = 100.0 * tot_dir / tot_val if tot_val else 0
        pe = 100.0 * tot_esq / tot_val if tot_val else 0
        print(f"{rotulo}: {len(linhas)} zonas | estado DIR {tot_dir:,} ({pd:.1f}%) "
              f"ESQ {tot_esq:,} ({pe:.1f}%) val {tot_val:,} -> {out.name}")

    # XLSX: 2 abas por cargo (ordenada por % Direita e por Votos DIR absolutos)
    try:
        from openpyxl import Workbook
        wb = Workbook(); wb.remove(wb.active)
        # rotulo curto por cargo p/ caber no limite de 31 chars da aba
        curto = {"Presidente 2T": "Presid", "Deputado Federal 1T": "DepFed"}
        for rotulo, (cols, linhas) in abas.items():
            c = curto.get(rotulo, rotulo[:10])
            for suf, chave in (("% Dir", lambda d: d["pct_dir"]),
                               ("Votos Dir", lambda d: d["vot_dir"])):
                ws = wb.create_sheet(f"{c} ({suf})"[:31])
                ws.append(cols)
                for d in sorted(linhas, key=chave, reverse=True):
                    ws.append([d[col] for col in cols])

        # aba "Locais": UNPIVOT - 1 linha por local, com stats de voto da zona
        dep = {d["nr_zona"]: d for d in abas.get("Deputado Federal 1T", ([], []))[1]}
        pres = {d["nr_zona"]: d for d in abas.get("Presidente 2T", ([], []))[1]}
        lp = ANALISE / f"locais_por_zona_sp_{ano}_geo.csv"
        if not lp.exists():
            lp = ANALISE / f"locais_por_zona_sp_{ano}.csv"
        loc_rows = list(csv.DictReader(lp.open(encoding="utf-8-sig"), delimiter=";"))
        lcols = ["nr_zona", "cd_municipio_tse", "nm_municipio", "nr_local_votacao",
                 "nm_local_votacao", "logradouro", "numero", "nm_bairro", "nr_cep",
                 "ds_endereco", "lat", "lon", "fonte_geo",
                 "dep_pct_dir", "dep_pct_esq", "dep_vencedor",
                 "pres_pct_dir", "pres_pct_esq", "pres_vencedor"]
        ws = wb.create_sheet("Locais")
        ws.append(lcols)
        for r in sorted(loc_rows, key=lambda r: (int(r["nr_zona"]), int(r["nr_local_votacao"]))):
            z = int(r["nr_zona"]); dd = dep.get(z, {}); pp = pres.get(z, {})
            logr, num = split_endereco(r.get("ds_endereco", ""))
            ws.append([r.get("nr_zona"), r.get("cd_municipio_tse"), r.get("nm_municipio"),
                       r.get("nr_local_votacao"), r.get("nm_local_votacao"), logr, num,
                       r.get("nm_bairro"), r.get("nr_cep"), r.get("ds_endereco"),
                       r.get("lat"), r.get("lon"), r.get("fonte_geo", ""),
                       dd.get("pct_dir", ""), dd.get("pct_esq", ""), dd.get("vencedor", ""),
                       pp.get("pct_dir", ""), pp.get("pct_esq", ""), pp.get("vencedor", "")])

        xlsx = ANALISE / "TOP Zonas por Votos - Presidente e Deputado (Direita e Esquerda) com Enderecos.xlsx"
        wb.save(xlsx)
        print(f"OK: {xlsx.name} ({len(wb.sheetnames)} abas: {wb.sheetnames})")
    except ImportError:
        print("(openpyxl indisponivel; XLSX pulado)")

    # amostra topo direita depfederal
    def asc(s): return str(s).encode("ascii", "replace").decode("ascii")
    print("\n=== TOP 5 zonas mais a DIREITA (Deputado Federal 2022) ===")
    for d in abas["Deputado Federal 1T"][1][:5]:
        print(f"  zona {d['nr_zona']} ({asc(d['municipio_sede'])}): {d['pct_dir']}% DIR | "
              f"{d['vot_dir']:,} votos | centro {d['centro_lat']},{d['centro_lon']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
