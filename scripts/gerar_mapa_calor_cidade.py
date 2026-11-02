#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_mapa_calor_cidade.py
FUNCAO    : Mapa de calor (choropleth Leaflet) das 645 cidades de SP por campo
            politico do PRESIDENTE (2014/2018/2022, 1T/2T). Metrica selecionavel:
            % Direita, % Esquerda, Votos DIR, Votos ESQ, Vencedor.
            Junta sp_municipios.geojson (cod IBGE 7 dig) com campo_presidente_*
            por municipio via dim_municipio (cd_municipio_tse -> cd_municipio_ibge).
SAIDAS    : data/analise/mapa_calor_cidade_presidente.html (autossuficiente)
USO       : python _scripts/gerar_mapa_calor_cidade.py
"""
import csv
import json
import sys
import webbrowser
from pathlib import Path

ANALISE = Path(r"D:/Dados_TSE/data/analise")
GEO = Path(r"D:/Dados_TSE/data/geo/sp_municipios.geojson")
ANOS = (2014, 2018, 2022)
TURNOS = (1, 2)

PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapa de Calor — Presidente SP por cidade</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  html,body { margin:0; height:100%; font-family: system-ui, Segoe UI, Arial, sans-serif; }
  #map { position:absolute; top:0; bottom:0; left:0; right:0; }
  .bar { position:absolute; z-index:1000; top:10px; left:52px; background:#fff; padding:8px 12px;
         border-radius:10px; box-shadow:0 1px 6px rgba(0,0,0,.3); font-size:13px; max-width:640px; }
  .bar h2 { margin:0 0 6px; font-size:15px; }
  .bar .row { display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin:3px 0; }
  select { padding:4px; border-radius:6px; border:1px solid #aaa; }
  .ctl { position:absolute; z-index:1000; top:150px; left:52px; width:232px; background:#fff;
         border-radius:10px; box-shadow:0 1px 6px rgba(0,0,0,.3); padding:8px 10px; font-size:12px;
         user-select:none; }
  .ctl-h { font-weight:600; cursor:move; margin-bottom:6px; padding-bottom:5px; border-bottom:1px solid #eee;
           display:flex; justify-content:space-between; align-items:center; }
  .ctl-h button { border:none; background:none; cursor:pointer; font-size:13px; color:#888; }
  .lg { font-size:12px; }
  .lg i { width:14px; height:14px; float:left; margin-right:6px; border:1px solid #999; }
  .pie { margin-top:8px; padding-top:6px; border-top:1px solid #eee; }
  .st { position:absolute; z-index:1000; bottom:26px; left:52px; background:#fff; padding:6px 10px;
        border-radius:10px; box-shadow:0 1px 6px rgba(0,0,0,.3); font-size:12px; }
</style>
</head>
<body>
<div id="map"></div>
<div class="bar">
  <h2>Presidente SP — por cidade</h2>
  <div class="row">
    <label>Ano <select id="ano"></select></label>
    <label>Turno <select id="turno"></select></label>
    <label>Métrica <select id="met">
      <option value="dir">% Direita</option>
      <option value="esq">% Esquerda</option>
      <option value="vdir">Votos DIR</option>
      <option value="vesq">Votos ESQ</option>
      <option value="w">Vencedor (campo)</option>
    </select></label>
    <button id="tb2" type="button" style="padding:4px 8px;border-radius:6px;border:1px solid #aaa;cursor:pointer;background:#f5f5f5;">Legenda</button>
    <button id="tb3" type="button" style="padding:4px 8px;border-radius:6px;border:1px solid #aaa;cursor:pointer;background:#f5f5f5;">Pizza</button>
  </div>
</div>
<div class="ctl" id="ctl" style="top:150px; left:52px;">
  <div class="ctl-h"><span>Legenda (arraste)</span><button id="ctlHide" type="button" title="Esconder">✕</button></div>
  <div class="lg" id="leg"></div>
</div>
<div class="ctl" id="ctl2" style="top:150px; left:355px; width:280px;">
  <div class="ctl-h"><span>Direita × Esquerda (arraste)</span><button id="ctl2Hide" type="button" title="Esconder">✕</button></div>
  <div class="pie" id="pie"></div>
</div>
<div class="st" id="st"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const GEO = __GEO__;
const DATA = __DATA__;
const LEGEND = {
  dir:  [[0,30,'#e8eefd'],[30,45,'#b8cdf8'],[45,55,'#7695ef'],[55,70,'#3a5fd9'],[70,101,'#0028a8']],
  esq:  [[0,30,'#fde8e8'],[30,45,'#f8b8b8'],[45,55,'#ef7676'],[55,70,'#d93a3a'],[70,101,'#a80000']],
  vdir: [[0,2000,'#f2f2f2'],[2000,10000,'#d8e4fd'],[10000,40000,'#7695ef'],[40000,150000,'#3a5fd9'],[150000,2e9,'#0028a8']],
  vesq: [[0,2000,'#f2f2f2'],[2000,10000,'#fdd8d8'],[10000,40000,'#ef7676'],[40000,150000,'#d93a3a'],[150000,2e9,'#a80000']]
};
const WCOL = {DIREITA:'#3a5fd9', ESQUERDA:'#d93a3a', CENTRO:'#8a8a8a', EMPATE:'#f2c12e', '':'#ddd'};

const map = L.map('map').setView([-22.15, -49.0], 6);
const BASES = {
  esri: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
         'Tiles &copy; Esri &mdash; Source: Esri'],
  carto: ['https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png',
          '&copy; OpenStreetMap &copy; CARTO'],
  osm: ['https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', '&copy; OpenStreetMap']
};
let tiles = null;
function baseNeutra() {
  document.getElementById('map').style.background = '#f4f2eb';
}
function addTiles(url, att) {
  if (tiles) { map.removeLayer(tiles); tiles = null; }
  if (!url) { baseNeutra(); return; }
  tiles = L.tileLayer(url, { attribution: att, maxZoom: 15 });
  tiles.on('tileerror', function () {
    if (!tiles) return;
    map.removeLayer(tiles); tiles = null;
    baseNeutra();
    const s = document.getElementById('tb');
    if (s) s.value = 'off';
  });
  tiles.addTo(map);
  baseNeutra();
}
function setBase(key) {
  if (key === 'off') { if (tiles) { map.removeLayer(tiles); tiles = null; } baseNeutra(); return; }
  const spec = BASES[key] || BASES.esri;
  addTiles(spec[0], spec[1]);
}
addTiles(BASES.esri[0], BASES.esri[1]);
const selT = document.createElement('select');
selT.id = 'tb';
selT.style.cssText = 'padding:4px;border-radius:6px;border:1px solid #aaa;';
selT.innerHTML = '<option value="esri" selected>Base: Esri</option>' +
                 '<option value="carto">Base: Carto</option>' +
                 '<option value="osm">Base: OSM</option>' +
                 '<option value="off">Fundo neutro</option>';
selT.addEventListener('change', function () { setBase(this.value); });
document.querySelector('.bar .row').appendChild(document.createTextNode(' '));
document.querySelector('.bar .row').appendChild(selT);

function fillColor(f, curriculumData) {
  const met = document.getElementById('met').value;
  const cod = f.properties.cod;
  const d = (curriculumData || {})[cod];
  if (met === 'w') {
    return WCOL[d ? d.w : ''] || WCOL[''];
  }
  if (!d) return '#ccc';
  const val = met === 'dir' ? d.pd : met === 'esq' ? d.pe : met === 'vdir' ? d.vd : d.ve;
  const bins = LEGEND[met];
  for (let i = 0; i < bins.length; i++) {
    if (val >= bins[i][0] && val < bins[i][1]) return bins[i][2];
  }
  return bins[bins.length - 1][2];
}

function valFor(f, curriculumData) {
  const met = document.getElementById('met').value;
  const d = (curriculumData || {})[f.properties.cod];
  if (!d) return null;
  if (met === 'dir') return d.pd;
  if (met === 'esq') return d.pe;
  if (met === 'vdir') return d.vd;
  if (met === 'vesq') return d.ve;
  return null;
}

let geoLayer = null;
function render() {
  const ano = document.getElementById('ano').value;
  const turno = document.getElementById('turno').value;
  const met = document.getElementById('met').value;
  const dd = (DATA[ano] || {})[turno] || {};
  if (geoLayer) map.removeLayer(geoLayer);
  geoLayer = L.geoJSON(GEO, {
    style: function (f) { return {
      fillColor: fillColor(f, dd), weight: 1, opacity: 1, color: '#fff', fillOpacity: 0.8
    }; },
    onEachFeature: function (f, layer) {
      const d = dd[f.properties.cod];
      const nm = f.properties.nome || f.properties.cod;
      const pop = f.properties.pop ? ' · pop ' + Number(f.properties.pop).toLocaleString('pt-BR') : '';
      let txt = '<b>' + nm + '</b>' + pop;
      if (d) {
        if (met === 'w') txt += '<br>Campo: <b>' + d.w + '</b>';
        else if (met.indexOf('v') === 0)
          txt += '<br>' + (met === 'vdir' ? 'DIR ' : 'ESQ ') + Number(valFor(f, dd)).toLocaleString('pt-BR') +
                 '<br>Válidos ' + Number(d.vd + d.ve).toLocaleString('pt-BR');
        else
          txt += '<br>' + (met === 'dir' ? 'Direita' : 'Esquerda') + ': <b>' +
                 valFor(f, dd).toFixed(1) + '%</b>' +
                 '<br>DIR ' + Number(d.vd).toLocaleString('pt-BR') +
                 ' · ESQ ' + Number(d.ve).toLocaleString('pt-BR');
      } else {
        txt += '<br><i>sem dados</i>';
      }
      layer.bindTooltip(txt, { sticky: true });
    }
  }).addTo(map);
  legend(met);
  summary(dd);
}

function legend(met) {
  const lg = document.getElementById('leg');
  if (met === 'w') {
    lg.innerHTML = '<b>Vencedor</b><br>' + ['DIREITA','ESQUERDA','CENTRO','EMPATE'].map(function (k) {
      return '<i style="background:' + WCOL[k] + '"></i>' + k + '<br>';
    }).join('');
    return;
  }
  const bins = LEGEND[met];
  const sufix = met.indexOf('%') === -1 && met.indexOf('v') === 0 ? '' : '%';
  lg.innerHTML = '<b>' + (met === 'dir' ? '% Direita' : met === 'esq' ? '% Esquerda' : met === 'vdir' ? 'Votos DIR' : 'Votos ESQ') + '</b><br>' +
    bins.map(function (b) {
      const hi = b[1] > 1e6 ? 'mais' : b[1];
      return '<i style="background:' + b[2] + '"></i>' + b[0] + ' – ' + hi + sufix + '<br>';
    }).join('');
}

function summary(dd) {
  let n = 0, svd = 0, sve = 0, svc = 0;
  for (const k in dd) { n++; const d = dd[k]; svd += d.vd; sve += d.ve; svc += d.vc; }
  const tot = svd + sve + svc;
  document.getElementById('st').innerHTML =
    (n ? n + ' cidades com dados · ' : '') +
    (tot ? 'DIR ' + svd.toLocaleString('pt-BR') + ' (' + (100 * svd / tot).toFixed(1) + '%) · ESQ ' +
    sve.toLocaleString('pt-BR') + ' (' + (100 * sve / tot).toFixed(1) + '%)' : '');
  renderPie(svd, sve, svc);
}

function renderPie(svd, sve, svc) {
  const el = document.getElementById('pie');
  const tot = svd + sve + svc;
  if (!tot) { el.innerHTML = '<div style="color:#888">sem dados</div>'; return; }
  const r = 26, C = 2 * Math.PI * r, W = 13;
  const direita = { c: '#3a5fd9', v: svd, n: 'Direita' };
  const esquerda = { c: '#d93a3a', v: sve, n: 'Esquerda' };
  const centro = { c: '#8a8a8a', v: svc, n: 'Centro' };
  const parts = svc > 0 ? [esquerda, centro, direita] : [esquerda, direita];
  let arcs = '', off = 0;
  for (const p of parts) {
    const frac = p.v / tot;
    arcs += '<circle cx="44" cy="44" r="' + r + '" fill="none" stroke="' + p.c + '" stroke-width="' + W +
            '" stroke-dasharray="' + (frac * C).toFixed(2) + ' ' + C.toFixed(2) +
            '" stroke-dashoffset="' + (-off).toFixed(2) + '" transform="rotate(-90 44 44)"/>';
    off += frac * C;
  }
  el.innerHTML = '<div style="display:flex;gap:10px;align-items:center">' +
    '<svg width="88" height="88" viewBox="0 0 88 88">' + arcs + '</svg>' +
    '<div>' + parts.map(function (p) {
      return '<div style="display:flex;align-items:center;margin:3px 0;font-size:12px">' +
        '<i style="width:11px;height:11px;background:' + p.c + ';display:inline-block;margin-right:6px;border-radius:2px"></i>' +
        p.n + ' <b style="margin-left:6px">' + (100 * p.v / tot).toFixed(1) + '%</b></div>';
    }).join('') + '</div></div>';
}

(function drag() {
  function makeCtl(ctlId, hideId, showId) {
    const ctl = document.getElementById(ctlId);
    let dragging = false, dx = 0, dy = 0;
    ctl.querySelector('.ctl-h').addEventListener('pointerdown', function (e) {
      dragging = true;
      const r = ctl.getBoundingClientRect();
      dx = e.clientX - r.left; dy = e.clientY - r.top;
      e.preventDefault();
    });
    window.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      ctl.style.left = (e.clientX - dx) + 'px';
      ctl.style.top = (e.clientY - dy) + 'px';
    });
    window.addEventListener('pointerup', function () { dragging = false; });
    document.getElementById(hideId).addEventListener('click', function () {
      ctl.style.display = 'none';
    });
    document.getElementById(showId).addEventListener('click', function () {
      ctl.style.display = 'block';
    });
  }
  makeCtl('ctl', 'ctlHide', 'tb2');
  makeCtl('ctl2', 'ctl2Hide', 'tb3');
})();

document.getElementById('ano').innerHTML = Object.keys(DATA).map(function (a) {
  return '<option value="' + a + '"' + (a === '2022' ? ' selected' : '') + '>' + a + '</option>';
}).join('');
document.getElementById('turno').innerHTML = ['1', '2'].map(function (t) {
  return '<option value="' + t + '"' + (t === '2' ? ' selected' : '') + '>Turno ' + t + '</option>';
}).join('');
['ano', 'turno', 'met'].forEach(function (id) {
  document.getElementById(id).addEventListener('change', render);
});
render();
</script>
</body>
</html>"""


def main():
    geo = json.loads(GEO.read_text(encoding="utf-8"))
    assert geo["type"] == "FeatureCollection" and len(geo["features"]) == 645

    import duckdb
    con = duckdb.connect(r"D:/Dados_TSE/data/db/sao_paulo.duckdb", read_only=True)
    mapa = {}
    for tse, ibge in con.execute(
        "SELECT cd_municipio_tse, cd_municipio_ibge FROM dim_municipio WHERE sg_uf='SP'"
    ).fetchall():
        mapa[str(int(tse))] = str(ibge)
    con.close()

    data = {str(a): {} for a in ANOS}
    total = 0
    for ano in ANOS:
        path = ANALISE / f"campo_presidente_{ano}_por_municipio.csv"
        with path.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                tse = str(int(row["cd_municipio_tse"]))
                if tse not in mapa:
                    continue
                ibge = mapa[tse]
                turno = str(row["nr_turno"])
                esq = int(row["vot_esq"] or 0)
                dir_ = int(row["vot_dir"] or 0)
                validos = int(row["validos"] or 0)
                data[str(ano)].setdefault(turno, {})[ibge] = {
                    "vd": dir_,
                    "ve": esq,
                    "vc": int(row["vot_cen"] or 0),
                    "pd": round(100.0 * dir_ / validos, 2) if validos else 0.0,
                    "pe": round(100.0 * esq / validos, 2) if validos else 0.0,
                    "w": row["vencedor_campo"],
                }
                total += 1
    print(f"municipios com dados por (ano,turno): {total} (esperado 645*3*2={645*3*2})")

    # propriedades extras que o mapa usa (pop) preservar; manter GEO enxuto
    geo_feats = [{
        "type": "Feature",
        "properties": {"cod": f["properties"]["cod"], "nome": f["properties"]["nome"],
                       "pop": f["properties"].get("pop")},
        "geometry": f["geometry"],
    } for f in geo["features"]]
    geo_out = {"type": "FeatureCollection", "features": geo_feats}

    out = ANALISE / "mapa_calor_cidade_presidente.html"
    html = (PAGE
            .replace("__GEO__", json.dumps(geo_out, ensure_ascii=False))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    out.write_text(html, encoding="utf-8")
    print(f"OK: mapa criado em {out} ({out.stat().st_size/1e6:.1f} MB)")
    webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())