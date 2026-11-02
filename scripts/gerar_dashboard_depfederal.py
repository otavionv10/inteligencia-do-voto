#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_dashboard_depfederal.py
FUNCAO    : Dashboard HTML autossuficiente: votos de DIREITA/ESQUERDA (Deputado
            Federal, SP) com nivel dinamico ESTADO | CIDADE | ZONA | SECAO,
            opcao agrupar on/off, metrica % Direita / % Esquerda / Votos DIR /
            Votos ESQ e busca por municipio. Dados embutidos em JSON.
SAIDAS    : data/analise/dashboard_depfederal.html
USO       : python _scripts/gerar_dashboard_depfederal.py
"""
import json
import sys
import webbrowser
from pathlib import Path

ANALISE = Path(r"D:/Dados_TSE/data/analise")
ANOS = (2014, 2018, 2022)
LIMITE_SECAO = 5000

# Reaproveita o PAGE do dashboard de presidente com o texto ajustado.
import importlib.util
_spec = importlib.util.spec_from_file_location("gdp", r"D:/Dados_TSE/_scripts/gerar_dashboard_presidente.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
PAGE = _mod.PAGE
PAGE = PAGE.replace(
    "<title>Presidente SP — Direita/Esquerda por Estado/Cidade/Zona/Seção</title>",
    "<title>Deputado Federal SP — Direita/Esquerda por Estado/Cidade/Zona/Seção</title>")
PAGE = PAGE.replace(
    "<h1>Presidente SP — Direita × Esquerda (2º turno)</h1>",
    "<h1>Deputado Federal SP — Direita × Esquerda (1º turno)</h1>")
PAGE = PAGE.replace(
    '<div class="sub">Campo = bloco com mais votos válidos (NOMINAL+LEGENDA; 95/96 excluídos) · nível Estado/Cidade/Zona/Seção · agregação usa TODAS as seções · fonte TSE/SP</div>',
    '<div class="sub">Campo = bloco com mais votos válidos (NOMINAL+LEGENDA; 95/96 excluídos) · nível Estado/Cidade/Zona/Seção · agregação usa TODAS as seções · Deputado Federal (1º turno) · fonte TSE/SP</div>')


def ler_secoes(ano):
    path = ANALISE / f"ranking_secao_direita_depfederal_{ano}_1t.csv"
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        hdrs = [h.strip().strip('"') for h in f.readline().rstrip("\n").split(";")]
        for line in f:
            vals = dict(zip(hdrs, [c.strip().strip('"') for c in line.rstrip("\n").split(";")]))
            validos = int(vals.get("validos", 0) or 0)
            dir_ = int(vals.get("vot_dir", 0) or 0)
            esq = int(vals.get("vot_esq", 0) or 0)
            rows.append([
                vals.get("nm_municipio_tse", ""),
                int(vals.get("nr_zona", 0) or 0),
                int(vals.get("nr_secao", 0) or 0),
                vals.get("local", ""),
                esq, dir_, validos,
                round(100.0 * dir_ / validos, 2) if validos else 0.0,
                round(100.0 * esq / validos, 2) if validos else 0.0,
            ])
    return rows


def agg_cidade(rows):
    a = {}
    for r in rows:
        e = a.get(r[0]) or [0, 0, 0, 0]
        a[r[0]] = [e[0] + 1, e[1] + r[4], e[2] + r[5], e[3] + r[6]]
    return [[k, n, esq, dd, vv,
             round(100.0 * dd / vv, 2) if vv else 0.0,
             round(100.0 * esq / vv, 2) if vv else 0.0]
            for k, (n, esq, dd, vv) in a.items()]


def agg_zona(rows):
    a = {}
    for r in rows:
        k = (r[0], r[1])
        e = a.get(k) or [0, 0, 0, 0]
        a[k] = [e[0] + 1, e[1] + r[4], e[2] + r[5], e[3] + r[6]]
    return [[k[0], k[1], n, esq, dd, vv,
             round(100.0 * dd / vv, 2) if vv else 0.0,
             round(100.0 * esq / vv, 2) if vv else 0.0]
            for k, (n, esq, dd, vv) in a.items()]


def agg_estado(rows):
    n = len(rows)
    esq = sum(r[4] for r in rows)
    dd = sum(r[5] for r in rows)
    vv = sum(r[6] for r in rows)
    return ["São Paulo (SP)", 645, n, esq, dd, vv,
            round(100.0 * dd / vv, 2) if vv else 0.0,
            round(100.0 * esq / vv, 2) if vv else 0.0]


def main():
    dados = {}
    for ano in ANOS:
        sec = ler_secoes(ano)
        sec_pct = sec[:LIMITE_SECAO]
        est = agg_estado(sec)
        cidade = agg_cidade(sec)
        zona = agg_zona(sec)
        dados[ano] = {"secao": sec_pct, "cidade": cidade, "zona": zona, "estado": [est]}
        print(f"{ano}: secao {len(sec)} | cidade {len(cidade)} | zona {len(zona)} | "
              f"estado ESQ {est[3]:,} DIR {est[4]:,} val {est[5]:,}")
    out = ANALISE / "dashboard_depfederal.html"
    out.write_text(PAGE.replace("__DADOS__", json.dumps(dados, ensure_ascii=False)),
                   encoding="utf-8")
    print(f"OK: dashboard criado em {out}")
    webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())