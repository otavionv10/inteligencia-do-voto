#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_dashboard_estado.py
FUNCAO    : Dashboard HTML autossuficiente POR ESTADO: campo politico
            (Direita/Esquerda/Centro) com nivel dinamico MUNICIPIO | ZONA |
            SECAO, metrica % Direita / % Esquerda / % Centro / Votos DIR / ESQ /
            Votos, e busca por municipio. Le os CSVs nacionais
            campo_brasil_por_secao.csv (detalhe) e campo_brasil_por_zona.csv.
Anos     : presidente T2: 2014/18/22 | depfederal T1: 2014/18/22
SAIDAS   : data/analise/dashboard_{cargo}_{UF}.html  (por estado)
USO      : python _scripts/gerar_dashboard_estado.py [--uf SP MG...]
Criado   : 2026-09-28
=============================================================================
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb

ANALISE = Path(__file__).resolve().parent.parent / "data" / "analise"
DB_BR = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
SEC = ANALISE / "campo_brasil_por_secao.csv"
ZON = ANALISE / "campo_brasil_por_zona.csv"
LIMITE_SECAO = 5000
CARGOS = {"presidente": 2, "depfederal": 1, "governador": 2}
LABEL = {"presidente": "Presidente", "depfederal": "Deputado Federal", "governador": "Governador"}
ANOS = (2014, 2018, 2022)

PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITULO}</title>
<style>
  body { font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 24px; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .sub { color: #888; font-size: 13px; margin-bottom: 18px; }
  .bar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
  .grp { margin-right: 6px; }
  button { padding: 7px 12px; border: 1px solid #999; border-radius: 8px;
           background: #eee; cursor: pointer; font-size: 13px; }
  button.on { background: #2d6cdf; color: #fff; border-color: #2d6cdf; font-weight: 600; }
  input { padding: 7px; border: 1px solid #999; border-radius: 8px; font-size: 13px; min-width: 210px; }
  label { font-size: 13px; user-select: none; }
  .count { font-size: 13px; color: #666; margin-left: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
  th { background: #f0f0f0; cursor: pointer; user-select: none; white-space: nowrap; }
  th.sorted { background: #dbeafe; }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .pipa { font-weight: 600; }
  .pos { color: #888; }
  @media (prefers-color-scheme: dark) {
    th { background: #2a2a2a; } th, td { border-color: #444; }
  }
</style>
</head>
<body>
<h1>{TITULO}</h1>
<div class="sub">{SUB}</div>

<div class="bar">
  <span class="grp"><strong>Ano:</strong></span>
  {ANO_BTN}
  <span class="grp" style="margin-left:12px"><strong>Nível:</strong></span>
  <button data-nivel="cidade" class="on" onclick="sel('nivel','cidade')">Município</button>
  <button data-nivel="zona" onclick="sel('nivel','zona')">Zona</button>
  <button data-nivel="secao" onclick="sel('nivel','secao')">Seção</button>
  <span class="grp" style="margin-left:12px"><strong>Ordenar:</strong></span>
  <button data-met="p" class="on" onclick="sel('met','p')">% Direita</button>
  <button data-met="e" onclick="sel('met','e')">% Esquerda</button>
  <button data-met="c" onclick="sel('met','c')">% Centro</button>
  <button data-met="d" onclick="sel('met','d')">Votos DIR</button>
  <button data-met="t" onclick="sel('met','t')">Votos ESQ</button>
  <label><input type="checkbox" id="agr" checked onclick="agrupar=this.checked;render()"> Agrupar</label>
  <input id="busca" placeholder="Filtrar por município..." oninput="render()">
  <span id="count" class="count"></span>
</div>

<table id="tbl"><thead></thead><tbody></tbody></table>

<script>
const DADOS = __DADOS__;
const COLS = {
  cidade: [{k:'pos',h:'#'},{k:'nm',h:'Município'},{k:'sec',h:'Seções',n:1},
           {k:'e',h:'Votos ESQ',n:1},{k:'c',h:'Votos CEN',n:1},{k:'d',h:'Votos DIR',n:1},{k:'v',h:'Válidos',n:1},{k:'p',h:'% ',n:1}],
  zona:   [{k:'pos',h:'#'},{k:'nm',h:'Município'},{k:'z',h:'Zona',n:1},{k:'sec',h:'Seções',n:1},
           {k:'e',h:'Votos ESQ',n:1},{k:'c',h:'Votos CEN',n:1},{k:'d',h:'Votos DIR',n:1},{k:'v',h:'Válidos',n:1},{k:'p',h:'% ',n:1}],
  secao:  [{k:'pos',h:'#'},{k:'nm',h:'Município'},{k:'z',h:'Zona',n:1},{k:'s',h:'Seção',n:1},
           {k:'e',h:'Votos ESQ',n:1},{k:'c',h:'Votos CEN',n:1},{k:'d',h:'Votos DIR',n:1},{k:'v',h:'Válidos',n:1},{k:'p',h:'% ',n:1}]
};
const I = {
  cidade: {nm:0,sec:1,e:2,c:3,d:4,v:5,pd:6,pe:7,pc:8},
  zona:   {nm:0,z:1,sec:2,e:3,c:4,d:5,v:6,pd:7,pe:8,pc:9},
  secao:  {nm:0,z:1,s:2,e:3,c:4,d:5,v:6,pd:7,pe:8,pc:9}
};
const UN = {cidade:'municípios', zona:'zonas', secao:'seções'};
const MET = {
  p: {key:'pd', pct:'pd', label:'% Direita'},
  e: {key:'pe', pct:'pe', label:'% Esquerda'},
  c: {key:'pc', pct:'pc', label:'% Centro'},
  d: {key:'d',  pct:'pd', label:'Votos DIR'},
  t: {key:'e',  pct:'pe', label:'Votos ESQ'}
};
let ano = 2022, nivel = 'cidade', met = 'p', agrupar = true, ordem = {k:null, inv:false};

function sel(name, v) {
  document.querySelectorAll('button[data-' + name + ']').forEach(b => b.classList.remove('on'));
  var t = document.querySelector('button[data-' + name + '="' + v + '"]');
  if (t) t.classList.add('on');
  if (name === 'ano') ano = v;
  if (name === 'nivel') nivel = v;
  if (name === 'met') met = v;
  render();
}
function fmt(v) { return v.toLocaleString('pt-BR'); }
function esc(s) {
  return String(s).replace(/[&<>"']/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}
function render() {
  var lvl = agrupar ? nivel : 'secao';
  var rows = (DADOS[ano] && DADOS[ano][lvl]) ? DADOS[ano][lvl].slice() : [];
  var m = MET[met];
  var fil = (document.getElementById('busca').value || '').toLowerCase().trim();
  if (fil) rows = rows.filter(function(r) { return String(r[0]).toLowerCase().indexOf(fil) !== -1; });

  var ksort = m.key;
  var nd = I[lvl][ksort];
  rows.sort(function(a, b) { return b[nd] - a[nd]; });

  if (ordem.k && ordem.k !== 'pos' && I[lvl][ordem.k] !== undefined) {
    var idx = I[lvl][ordem.k];
    rows.sort(function(a, b) {
      var x = a[idx], y = b[idx];
      if (typeof x === 'number' && typeof y === 'number') return ordem.inv ? y - x : x - y;
      return ordem.inv ? String(y).localeCompare(String(x)) : String(x).localeCompare(String(y));
    });
  }
  var cols = COLS[lvl].map(function(c) {
    return c.k === 'p' ? {k:'p', h:'% ' + m.label, n:1} : c;
  });
  document.querySelector('#tbl thead').innerHTML =
    '<tr>' + cols.map(function(c) {
      return '<th data-k="' + c.k + '"' + (c.n ? ' class="n"' : '') + '>' + esc(c.h) + '</th>';
    }).join('') + '</tr>';
  document.querySelectorAll('#tbl th').forEach(function(th) {
    th.classList.toggle('sorted', (ordem.k === th.dataset.k) || (!ordem.k && th.dataset.k === ksort));
  });
  var pctIx = I[lvl][m.pct];
  document.getElementById('count').textContent = rows.length + ' ' + UN[lvl];
  document.querySelector('#tbl tbody').innerHTML = rows.map(function(r, i) {
    var cells = '<td class="pos">' + (i + 1) + '</td>';
    for (var j = 1; j < cols.length; j++) {
      var c = cols[j];
      if (c.k === 'pos') continue;
      var v = r[I[lvl][c.k]];
      if (c.k === 'p') cells += '<td class="n">' + (v === null || v === undefined ? '' : v.toFixed(2).replace('.', ',') + '%') + '</td>';
      else if (c.k === 'nm') cells += '<td class="pipa">' + esc(v) + '</td>';
      else if (c.k === 'local') cells += '<td>' + esc(v) + '</td>';
      else cells += '<td class="n">' + (typeof v === 'number' ? fmt(v) : esc(v)) + '</td>';
    }
    return '<tr>' + cells + '</tr>';
  }).join('');
}
document.querySelector('#tbl thead').addEventListener('click', function(ev) {
  var th = ev.target.closest('th');
  if (!th) return;
  var k = th.dataset.k;
  if (ordem.k === k) ordem.inv = !ordem.inv;
  else ordem = {k: k, inv: false};
  render();
});
render();
</script>
</body>
</html>"""


def ler_csv(path):
    """Retorna lista de dicts (UTF-8 BOM, ';' ou ',', header)."""
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        line = f.readline()
        sep = ";" if line.count(";") > line.count(",") else ","
        hdrs = [h.strip().strip('"') for h in line.rstrip("\n").split(sep)]
        for line in f:
            vals = dict(zip(hdrs, [c.strip().strip('"') for c in line.rstrip("\n").split(sep)]))
            rows.append(vals)
    return rows


def sel(rows, uf, cargo, ano, turno):
    return [r for r in rows
            if r.get("sg_uf") == uf and r.get("cargo") == cargo
            and r.get("ano_eletivo") == str(ano) and r.get("nr_turno") == str(turno)]


def to_num(v):
    try:
        return int(float(v or 0))
    except (ValueError, TypeError):
        return 0


def ler_csv_idx(path):
    """Streaming: agrupa linhas por (uf, cargo, ano, turno) em tuplas compactas.
    Retorna (indice, conjunto_ufs)."""
    idx = {}
    ufs = set()
    cod2nm = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        line = f.readline()
        sep = ";" if line.count(";") > line.count(",") else ","
        hdr = [h.strip().strip('"') for h in line.rstrip("\n").split(sep)]
        im = {h: i for i, h in enumerate(hdr)}

        def g(vals, key):
            try:
                return vals[im[key]]
            except KeyError:
                return ""

        for line in f:
            vals = [c.strip().strip('"') for c in line.rstrip("\n").split(sep)]
            u = g(vals, "sg_uf")
            if not u:
                continue
            ufs.add(u)
            k = (u, g(vals, "cargo"), g(vals, "ano_eletivo"), g(vals, "nr_turno"))
            if "nr_secao" in im:
                row = (g(vals, "cd_municipio_tse"), to_num(g(vals, "nr_zona")),
                       to_num(g(vals, "nr_secao")),
                       to_num(g(vals, "vot_esq")), to_num(g(vals, "vot_cen")),
                       to_num(g(vals, "vot_dir")), to_num(g(vals, "validos")))
                if g(vals, "nm_municipio_tse"):
                    cod2nm[g(vals, "cd_municipio_tse")] = g(vals, "nm_municipio_tse")
            else:
                row = (g(vals, "cd_municipio_tse"), to_num(g(vals, "nr_zona")),
                       to_num(g(vals, "vot_esq")), to_num(g(vals, "vot_cen")),
                       to_num(g(vals, "vot_dir")), to_num(g(vals, "validos")))
            idx.setdefault(k, []).append(row)
    return idx, ufs, cod2nm


LAT = {"presidente": "presidente", "depfederal": "deputado federal", "governador": "governador"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", nargs="+", help="UFs (padrao: todas no CSV secao)")
    ap.add_argument("--cargo", nargs="+", choices=list(CARGOS),
                    help="cargos a gerar (padrao: todos)")
    args = ap.parse_args()

    if args.cargo:
        cargos = {c: CARGOS[c] for c in args.cargo}
    else:
        cargos = CARGOS

    print("carregando CSVs (secao/zona) em streaming ...")
    sec_idx, ufs_all, _ = ler_csv_idx(SEC)
    zon_idx, _, _ = ler_csv_idx(ZON)
    nsec = sum(len(v) for v in sec_idx.values())
    nzon = sum(len(v) for v in zon_idx.values())
    print(f"  secao {nsec:,} | zona {nzon:,}")

    cod2nm = {}
    try:
        con = duckdb.connect(str(DB_BR), read_only=True)
        cod2nm = {str(r[0]): r[1] for r in con.execute(
            "SELECT cd_municipio_tse, nm_municipio_tse FROM dim_municipio").fetchall()}
        con.close()
    except Exception:
        pass

    if args.uf:
        ufs = sorted({u.upper() for u in args.uf})
    else:
        ufs = sorted(ufs_all)
    print(f"UFs: {len(ufs)}")

    for uf in ufs:
        for cargoslug, turno in cargos.items():
            if cargoslug not in LAT:
                continue
            cargo = LAT[cargoslug]
            dados = {}
            for ano in ANOS:
                k = (uf, cargo, str(ano), str(turno))
                secs = sec_idx.get(k, [])
                if cargoslug == "governador" and not secs:
                    k = (uf, cargo, str(ano), "1")
                    secs = sec_idx.get(k, [])
                zons = zon_idx.get(k, [])
                # municipio agg  (sec tuples: codmun, zona, secao, esq, cen, dir, validos)
                agg = {}
                for r in secs:
                    m = cod2nm.get(r[0], r[0])
                    e = agg.get(m) or [0, 0, 0, 0, 0]
                    agg[m] = [e[0] + 1, e[1] + r[3], e[2] + r[4], e[3] + r[5], e[4] + r[6]]
                cidade = [[m, n, esq, cen, dd, vv,
                           round(100.0 * dd / vv, 2) if vv else 0.0,
                           round(100.0 * esq / vv, 2) if vv else 0.0,
                           round(100.0 * cen / vv, 2) if vv else 0.0]
                          for m, (n, esq, cen, dd, vv) in agg.items()]
                # zona (zon tuples: nm, zona, esq, cen, dir, validos) + contagem de secoes
                cnt_sec_zona = {}
                for r in secs:
                    nm = cod2nm.get(r[0], r[0])
                    q = (nm, r[1])
                    cnt_sec_zona[q] = cnt_sec_zona.get(q, 0) + 1
                zona = []
                for r in zons:
                    vv = r[5]
                    nm = cod2nm.get(r[0], r[0])
                    zona.append([
                        nm, r[1], cnt_sec_zona.get((nm, r[1]), 0),
                        r[2], r[3], r[4], vv,
                        round(100.0 * r[4] / vv, 2) if vv else 0.0,
                        round(100.0 * r[2] / vv, 2) if vv else 0.0,
                        round(100.0 * r[3] / vv, 2) if vv else 0.0,
                    ])
                # secao (limite)
                sec_list = []
                for r in secs:
                    vv = r[6]
                    sec_list.append([
                        cod2nm.get(r[0], r[0]), r[1], r[2],
                        r[3], r[4], r[5], vv,
                        round(100.0 * r[5] / vv, 2) if vv else 0.0,
                        round(100.0 * r[3] / vv, 2) if vv else 0.0,
                        round(100.0 * r[4] / vv, 2) if vv else 0.0,
                    ])
                sec_list.sort(key=lambda x: (x[7], x[8], x[9]), reverse=True)
                dados[ano] = {"cidade": cidade, "zona": zona,
                              "secao": sec_list[:LIMITE_SECAO]}
                total_dir = sum(r[5] for r in secs)
                print(f"  {uf} {cargoslug} {ano}: cidade {len(cidade)} | zona {len(zona)} | "
                      f"secao {len(secs):,} | DIR total {total_dir:,}")

            titulo = f"{LABEL[cargoslug]} {uf} — Direita × Esquerda"
            sub = (f"Campo = bloco com mais votos válidos (NOMINAL+LEGENDA; 95/96/97 excl.) · "
                   f"nível Município/Zona/Seção · fonte TSE/BRASIL ({uf})")
            ano_btn = "".join(
                f'<button data-ano="{a}"' + (" class=\"on\"" if a == 2022 else "")
                + f' onclick="sel(\'ano\',{a})">{a}</button>' for a in ANOS)
            html = (PAGE.replace("{TITULO}", titulo)
                        .replace("{SUB}", sub)
                        .replace("{ANO_BTN}", ano_btn)
                        .replace("__DADOS__", json.dumps(dados, ensure_ascii=False)))
            out = ANALISE / f"dashboard_{cargoslug}_{uf}.html"
            out.write_text(html, encoding="utf-8")
            print(f"  OK {out.name} ({out.stat().st_size/1e6:.1f} MB)")
    print("fim.")


if __name__ == "__main__":
    sys.exit(main())