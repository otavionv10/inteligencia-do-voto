#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_analises_socio_uf.py
FUNCAO    : Analises socioeleitorais POR UF a partir do brasil.duckdb:
            (A) Abstencao e comparecimento por eleicao/ano (fact_votacao_secao)
            (B) Perfil do eleitorado por sexo/faixa etaria/escolaridade/cor
                (fact_eleitorado_perfil, 2022/2024; slice por secao)
            (C) Voto x indicadores: campo politico por municipio (presidente
                2022 T2 e depfederal 2022 T1) cruzado com IBGE (pop, PIB pc,
                IDHM) do dim_municipio enriquecido. Correlacao (Spearman/Pearson)
                por UF e para o BR.
SAIDAS   : data/analise/socio_uf/{UF}/
                01_abstencao_{UF}.csv
                02_perfil_eleitorado_{UF}.csv
                03_voto_x_indicadores_{UF}.csv
                04_correlacoes_{UF}.csv
              socio_uf/relatorio_socio_{UF}.html     (dashboard resumo)
              socio_uf/correlacoes_brasil.csv
USO      : python _scripts/gerar_analises_socio_uf.py [--uf SP]
Criado   : 2026-09-28
=============================================================================
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
OUT = Path(__file__).resolve().parent.parent / "data" / "analise" / "socio_uf"


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    d1 = sum((a - mx) ** 2 for a in xs) ** 0.5
    d2 = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (d1 * d2) if d1 and d2 else None


def rho(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    rx = {v: i for i, v in enumerate(sorted(xs))}
    ry = {v: i for i, v in enumerate(sorted(ys))}
    dx = [rx[v] for v in xs]
    dy = [ry[v] for v in ys]
    return corr(dx, dy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", nargs="+", help="UFs (padrao: todas)")
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    if args.uf:
        ufs = sorted({u.upper() for u in args.uf})
    else:
        ufs = [r[0] for r in con.execute(
            "SELECT DISTINCT sg_uf FROM dim_municipio ORDER BY 1").fetchall()]

    # ---- (C) agregado municipio 2022 para correlacao, todo o BR ----
    mun_all = {}
    for r in con.execute("""
        WITH base AS (
            SELECT v.cd_municipio_tse, m.sg_uf, v.nr_turno, v.ds_cargo, v.qt_votos,
                   COALESCE(c1.campo, c2.campo, p.campo) AS campo
            FROM fact_votacao_secao v
            JOIN dim_municipio m USING (cd_municipio_tse)
            LEFT JOIN vw_candidato_campo c1
                   ON c1.ano_eletivo = v.ano_eletivo AND c1.sq_candidato = v.sq_candidato
            LEFT JOIN vw_candidato_campo c2
                   ON c2.ano_eletivo = v.ano_eletivo
                  AND c2.nr_candidato = v.nr_votavel
                  AND upper(c2.ds_cargo) = upper(v.ds_cargo)
                  AND c2.sg_uf = CASE WHEN upper(v.ds_cargo) = 'PRESIDENTE'
                                      THEN 'BR' ELSE COALESCE(m.sg_uf, '--') END
            LEFT JOIN dim_campo_partido p
                   ON p.nr_partido = v.nr_votavel AND COALESCE(v.sq_candidato, -1) < 0
            WHERE v.ano_eletivo = 2022 AND v.nr_votavel NOT IN (95, 96, 97)
              AND upper(v.ds_cargo) IN ('PRESIDENTE', 'DEPUTADO FEDERAL')
        )
        SELECT sg_uf, cd_municipio_tse, ds_cargo, nr_turno, campo, SUM(qt_votos) vot
        FROM base
        GROUP BY 1, 2, 3, 4, 5
    """).fetchall():
        sg, cd, cargo, turno, campo, vot = r
        mun_all.setdefault((cd, cargo, turno), {"sg_uf": sg, "esq": 0, "dir": 0})
        d = mun_all[(cd, cargo, turno)]
        if campo == "ESQUERDA":
            d["esq"] += vot
        elif campo == "DIREITA":
            d["dir"] += vot

    ind = {}
    for r in con.execute("""
        SELECT cd_municipio_tse, ibge_pop_2022, ibge_pib_pc_2023, ibge_idhm_2010
        FROM dim_municipio
    """).fetchall():
        ind[r[0]] = (r[1], r[2], r[3])

    for uf in ufs:
        d = OUT / uf
        d.mkdir(parents=True, exist_ok=True)

        # ---- (A) abstencao / comparecimento ----
        # aptos vem de fact_eleitorado_local (eleitorado por secao) e
        # comparecimento = SOMA de todos os votos do turno (valido+legenda+branco+nulo),
        # via cargo de referencia do turno. Disponivel para 2022/2024 (anos com
        # fact_eleitorado_local no banco BR).
        with (d / f"01_abstencao_{uf}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["sg_uf", "ano_eletivo", "cargo_referencia", "nr_turno",
                        "qt_aptos", "qt_comparecimento", "qt_abstencoes",
                        "pct_comparecimento", "pct_abstencao"])
            ele_local = con.execute("""
                SELECT e.nr_turno, SUM(e.qt_eleitor_secao)
                FROM fact_eleitorado_local e JOIN dim_municipio m USING (cd_municipio_tse)
                WHERE m.sg_uf = ? AND e.ano_eletivo = 2022
                GROUP BY 1 ORDER BY 1
            """, [uf]).fetchall()
            aptos = {r[0]: r[1] for r in ele_local}
            for r in con.execute("""
                SELECT upper(v.ds_cargo) AS cargo, v.nr_turno, SUM(v.qt_votos)
                FROM fact_votacao_secao v JOIN dim_municipio m USING (cd_municipio_tse)
                WHERE m.sg_uf = ? AND v.ano_eletivo = 2022
                  AND upper(v.ds_cargo) IN ('PRESIDENTE', 'GOVERNADOR')
                  AND v.nr_votavel IS NOT NULL
                GROUP BY 1, 2 ORDER BY 2, 1
            """, [uf]).fetchall():
                cargo, turno, tot = r
                ap = aptos.get(turno)
                if ap is None:
                    continue
                ab = ap - tot if tot is not None else None
                w.writerow([uf, 2022, cargo, turno, ap, tot,
                            ab,
                            round(100.0 * tot / ap, 2) if ap else "",
                            round(100.0 * ab / ap, 2) if ap else ""])

        # ---- (B) perfil do eleitorado (2022) ----
        with (d / f"02_perfil_eleitorado_{uf}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["sg_uf", "ano_eletivo", "dimensao", "categoria",
                        "qt_eleitores_perfil", "pct"])
            for dim, col in [("sexo", "ds_genero"), ("faixa_etaria", "ds_faixa_etaria"),
                             ("escolaridade", "ds_grau_escolaridade"),
                             ("cor_raca", "ds_cor_raca")]:
                rows = con.execute(f"""
                    SELECT m.sg_uf, e.ano_eletivo, e.{col} AS cat,
                           SUM(e.qt_eleitores_perfil) tot
                    FROM fact_eleitorado_perfil e JOIN dim_municipio m USING (cd_municipio_tse)
                    WHERE m.sg_uf = ? AND e.ano_eletivo = 2022 AND e.{col} IS NOT NULL
                    GROUP BY 1, 2, 3
                """, [uf]).fetchall()
                tot = sum(r[3] for r in rows)
                for sg, ano, cat, q in rows:
                    w.writerow([sg, ano, dim, (cat or "").strip(),
                                q, round(100.0 * q / tot, 3) if tot else ""])

        # ---- (C) voto x indicadores ----
        with (d / f"03_voto_x_indicadores_{uf}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["sg_uf", "cd_municipio_tse", "cargo", "nr_turno",
                        "vot_dir", "vot_esq", "validos", "share_dir", "share_esq",
                        "ibge_pop_2022", "ibge_pib_pc_2023", "ibge_idhm_2010"])
            for (cd, cargo, turno), d0 in mun_all.items():
                if d0["sg_uf"] != uf:
                    continue
                iv = ind.get(cd)
                if not iv:
                    continue
                vv = d0["dir"] + d0["esq"]
                w.writerow([uf, cd, cargo, turno, d0["dir"], d0["esq"], vv,
                            round(100.0 * d0["dir"] / vv, 2) if vv else "",
                            round(100.0 * d0["esq"] / vv, 2) if vv else "",
                            *iv])

        # ---- correlacoes ----
        corrs = []
        for cargo, turno in (("PRESIDENTE", 2), ("DEPUTADO FEDERAL", 1)):
            us = [(k, v) for k, v in mun_all.items() if k[1] == cargo and k[2] == turno and v["sg_uf"] == uf]
            xs_pop, xs_pib, xs_idh, yd, ye = [], [], [], [], []
            for (cd, c, t), v in us:
                iv = ind.get(cd)
                if not iv:
                    continue
                vv = v["dir"] + v["esq"]
                if vv <= 0:
                    continue
                sd = 100.0 * v["dir"] / vv
                if iv[0] is not None:
                    xs_pop.append(iv[0]); yd.append(sd)
                if iv[1] is not None:
                    xs_pib.append(iv[1]); yd.append(sd)
                if iv[2] is not None:
                    xs_idh.append(iv[2]); yd.append(sd)
            base = [("PRESIDENTE" if cargo == "PRESIDENTE" else "DEP. FEDERAL", turno)]
            corrs.append([uf, cargo, turno, "share_dir x pop_2022", len(xs_pop), corr(xs_pop, yd), rho(xs_pop, yd)])
            corrs.append([uf, cargo, turno, "share_dir x pib_pc_2023", len(xs_pib), corr(xs_pib, yd), rho(xs_pib, yd)])
            corrs.append([uf, cargo, turno, "share_dir x idhm_2010", len(xs_idh), corr(xs_idh, yd), rho(xs_idh, yd)])
        with (d / f"04_correlacoes_{uf}.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["sg_uf", "cargo", "nr_turno", "par", "n", "pearson_r", "spearman_rho"])
            w.writerows(corrs)
        print(f"  {uf}: abstenção+perfil+votoxind+correlações OK")

        # ---- relatorio HTML ----
        build_relatorio(d, uf, ufs)

    con.close()
    print("fim.")


def build_relatorio(d, uf, _ufs):
    absten = []
    pth = d / f"01_abstencao_{uf}.csv"
    if pth.exists():
        with pth.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                absten.append(row)
    perfil = {}
    pth = d / f"02_perfil_eleitorado_{uf}.csv"
    if pth.exists():
        with pth.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                perfil.setdefault(row["dimensao"], []).append(row)
    vxi = []
    pth = d / f"03_voto_x_indicadores_{uf}.csv"
    if pth.exists():
        with pth.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                vxi.append(row)
    corrs = []
    pth = d / f"04_correlacoes_{uf}.csv"
    if pth.exists():
        with pth.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                corrs.append(row)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Análises socioeleitorais — {uf}</title>
<style>
 body {{ font-family: system-ui,Segoe UI,Arial,sans-serif; margin: 24px; }}
 h1 {{ font-size: 22px; }} h2 {{ font-size: 17px; margin-top: 28px; border-bottom: 2px solid #333; padding-bottom: 4px; }}
 table {{ border-collapse: collapse; font-size: 12.5px; margin: 8px 0; }}
 th,td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
 th {{ background: #efefef; }} td.n, th.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
</style></head><body>
<h1>Análises socioeleitorais — {uf}</h1>
<p>Fonte: TSE (votação por seção, perfil do eleitorado) + IBGE (Censo 2022, PIB 2023) + Atlas PNUD (IDHM 2010).</p>
"""
    html += "<h2>1. Comparecimento / abstenção</h2><table><tr>"
    for h in ("Ano", "Cargo", "Turno", "Aptos", "Comparecimento", "Abstenções", "% compareceu", "% abstenção"):
        html += f"<th>{h}</th>"
    html += "</tr>"
    for r in absten:
        html += "<tr>"
        for k in ("ano_eletivo", "cargo_referencia", "nr_turno", "qt_aptos", "qt_comparecimento",
                  "qt_abstencoes", "pct_comparecimento", "pct_abstencao"):
            html += f"<td class=\"n\">{r.get(k, '')}</td>"
        html += "</tr>"
    html += "</table>"

    html += "<h2>2. Perfil do eleitorado 2022</h2>"
    titulos = {"sexo": "Sexo", "faixa_etaria": "Faixa etária",
               "escolaridade": "Escolaridade", "cor_raca": "Cor/Raça"}
    for dim in ("sexo", "faixa_etaria", "escolaridade", "cor_raca"):
        rows = perfil.get(dim, [])
        html += f"<h3>{titulos[dim]}</h3><table><tr><th>Categoria</th><th class=\"n\">Eleitores</th><th class=\"n\">%</th></tr>"
        for r in rows:
            html += (f"<tr><td>{r['categoria']}</td>"
                     f"<td class=\"n\">{r['qt_eleitores_perfil']}</td>"
                     f"<td class=\"n\">{r['pct']}%</td></tr>")
        html += "</table>"

    html += "<h2>3. Voto × indicadores (2022)</h2>"
    for cslug, tslug in (("PRESIDENTE", "2"), ("DEPUTADO FEDERAL", "1")):
        cname = "Presidente" if cslug == "PRESIDENTE" else "Deputado Federal"
        html += f"<h3>{cname} T{tslug}</h3><table><tr>"
        for h in ("Município", "Votos DIR", "Votos ESQ", "% DIR", "% ESQ", "Pop 2022", "PIB pc", "IDHM"):
            html += f"<th>{h}</th>"
        html += "</tr>"
        for r in vxi:
            if r.get("cargo", "").upper() != cslug or r.get("nr_turno") != tslug:
                continue
            html += (f"<tr><td class=\"n\">{r['cd_municipio_tse']}</td>"
                     f"<td class=\"n\">{r['vot_dir']}</td><td class=\"n\">{r['vot_esq']}</td>"
                     f"<td class=\"n\">{r['share_dir']}%</td><td class=\"n\">{r['share_esq']}%</td>"
                     f"<td class=\"n\">{r['ibge_pop_2022']}</td><td class=\"n\">{r['ibge_pib_pc_2023']}</td>"
                     f"<td class=\"n\">{r['ibge_idhm_2010']}</td></tr>")
        html += "</table>"

    html += "<h2>4. Correlações (% direita × indicador)</h2><table><tr>"
    for h in ("Cargo", "Turno", "Par", "n", "Pearson r", "Spearman ρ"):
        html += f"<th>{h}</th>"
    html += "</tr>"
    for r in corrs:
        html += (f"<tr><td>{r['cargo']}</td><td class=\"n\">{r['nr_turno']}</td>"
                 f"<td>{r['par']}</td><td class=\"n\">{r['n']}</td>"
                 f"<td class=\"n\">{r['pearson_r']}</td><td class=\"n\">{r['spearman_rho']}</td></tr>")
    html += "</table>"
    html += "</body></html>"
    out = OUT / f"relatorio_socio_{uf}.html"
    out.write_text(html, encoding="utf-8")
    print(f"    OK relatorio_socio_{uf}.html")


if __name__ == "__main__":
    sys.exit(main())