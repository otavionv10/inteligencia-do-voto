#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_dashboard_presidente.py
FUNCAO    : Dashboard HTML autossuficiente: votos de DIREITA/ESQUERDA (presidente,
            SP, por turno) com nivel dinamico ESTADO | CIDADE | ZONA | SECAO,
            opcao agrupar on/off, metrica % Direita / % Esquerda / Votos DIR / Votos ESQ
            e busca por municipio. Dados embutidos em JSON.
            Agregacoes de cidade/zona/estado somam TODAS as secoes.
SAIDAS    : data/analise/dashboard_presidente.html
USO       : python _scripts/gerar_dashboard_presidente.py
"""
import json
import sys
import webbrowser
from pathlib import Path

ANALISE = Path(r"D:/Dados_TSE/data/analise")
ANOS = (2014, 2018, 2022)
LIMITE_SECAO = 5000

PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Presidente SP — Direita/Esquerda por Estado/Cidade/Zona/Seção</title>
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
<h1>Presidente SP — Direita × Esquerda (2º turno)</h1>
<div class="sub">Campo = bloco com mais votos válidos (NOMINAL+LEGENDA; 95/96 excluídos) · nível Estado/Cidade/Zona/Seção · agregação usa TODAS as seções · fonte TSE/SP</div>

<div class="bar">
  <span class="grp"><strong>Ano:</strong></span>
  <button data-ano="2014" onclick="sel('ano',2014)">2014</button>
  <button data-ano="2018" onclick="sel('ano',2018)">2018</button>
  <button data-ano="2022" class="on" onclick="sel('ano',2022)">2022</button>
  <span class="grp" style="margin-left:12px"><strong>Nível:</strong></span>
  <button data-nivel="estado" onclick="sel('nivel','estado')">Estado</button>
  <button data-nivel="cidade" class="on" onclick="sel('nivel','cidade')">Cidade</button>
  <button data-nivel="zona" onclick="sel('nivel','zona')">Zona</button>
  <button data-nivel="secao" onclick="sel('nivel','secao')">Seção</button>
  <span class="grp" style="margin-left:12px"><strong>Ordenar:</strong></span>
  <button data-met="p" class="on" onclick="sel('met','p')">% Direita</button>
  <button data-met="e" onclick="sel('met','e')">% Esquerda</button>
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
  estado: [{k:'pos',h:'#'},{k:'nm',h:'Estado'},{k:'mun',h:'Municípios',n:1},{k:'sec',h:'Seções',n:1},
           {k:'e',h:'Votos ESQ',n:1},{k:'d',h:'Votos DIR',n:1},{k:'v',h:'Válidos',n:1},{k:'p',h:'% ',n:1}],
  cidade: [{k:'pos',h:'#'},{k:'nm',h:'Município'},{k:'sec',h:'Seções',n:1},
           {k:'e',h:'Votos ESQ',n:1},{k:'d',h:'Votos DIR',n:1},{k:'v',h:'Válidos',n:1},{k:'p',h:'% ',n:1}],
  zona:   [{k:'pos',h:'#'},{k:'nm',h:'Município'},{k:'z',h:'Zona',n:1},{k:'sec',h:'Seções',n:1},
           {k:'e',h:'Votos ESQ',n:1},{k:'d',h:'Votos DIR',n:1},{k:'v',h:'Válidos',n:1},{k:'p',h:'% ',n:1}],
  secao:  [{k:'pos',h:'#'},{k:'nm',h:'Município'},{k:'z',h:'Zona',n:1},{k:'s',h:'Seção',n:1},
           {k:'local',h:'Local'},{k:'e',h:'Votos ESQ',n:1},{k:'d',h:'Votos DIR',n:1},{k:'v',h:'Válidos',n:1},{k:'p',h:'% ',n:1}]
};
const I = {
  estado: {nm:1,mun:2,sec:3,e:4,d:5,v:6,pd:7,pe:8},
  cidade: {nm:0,sec:1,e:2,d:3,v:4,pd:5,pe:6},
  zona:   {nm:0,z:1,sec:2,e:3,d:4,v:5,pd:6,pe:7},
  secao:  {nm:0,z:1,s:2,local:3,e:4,d:5,v:6,pd:7,pe:8}
};
const UN = {estado:'estado', cidade:'cidades', zona:'zonas', secao:'seções'};
const MET = {
  p: {key:'pd', pct:'pd', label:'% Direita'},
  e: {key:'pe', pct:'pe', label:'% Esquerda'},
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
  var rows = DADOS[ano][lvl].slice();
  var m = MET[met];
  var fil = (document.getElementById('busca').value || '').toLowerCase().trim();
  if (fil) rows = rows.filter(function(r) { return String(r[0]).toLowerCase().indexOf(fil) !== -1; });

  /* ordenacao padrao pela metrica ativa (sobe: pct desc para p/e, total desc para d/t) */
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


def ler_secoes(ano):
    path = ANALISE / f"ranking_secao_direita_{ano}_2t.csv"
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
    out = ANALISE / "dashboard_presidente.html"
    out.write_text(PAGE.replace("__DADOS__", json.dumps(dados, ensure_ascii=False)),
                   encoding="utf-8")
    print(f"OK: dashboard criado em {out}")
    webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())