#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_mapa_estado.py
FUNCAO    : Mapa coropletico por ESTADO (igual conceito do SP) mostrando cada
            municipio, campo politico (ESQ/CEN/DIR). P/ todos os estados, todos
            os anos (2012-2024) e cargos presentes no banco BRASIL.
            Junta data/geo/uf/{UF}_municipios.geojson (malha IBGE 2025) com
            campo_municipio_brasil_por_cargo.csv por cd_municipio_ibge.
SAIDAS    : data/analise/mapa_estado_{UF}.html  (autossuficiente, 1 p/ estado)
USO       :
    python _scripts/gerar_mapa_estado.py                 # todos estados
    python _scripts/gerar_mapa_estado.py SP MG           # so SP e MG
=============================================================================
"""
import csv
import json
import sys
import webbrowser
from pathlib import Path

import duckdb

DB = r"D:/Dados_TSE/data/db/brasil.duckdb"
ANALISE = Path(r"D:/Dados_TSE/data/analise")
GEO_DIR = Path(r"D:/Dados_TSE/data/geo/uf")
CSV = ANALISE / "campo_municipio_brasil_por_cargo.csv"
MAPA_OUT = ANALISE / "mapa_estado_{uf}.html"

CENTROS = {
    "AC": (-9.5, -70.5), "AL": (-9.6, -36.8), "AM": (-4.0, -63.5), "AP": (1.5, -52.0),
    "BA": (-12.5, -42.0), "CE": (-5.2, -39.7), "DF": (-15.8, -47.9), "ES": (-19.5, -40.5),
    "GO": (-15.8, -49.5), "MA": (-5.0, -45.0), "MG": (-18.0, -44.0), "MS": (-20.0, -54.5),
    "MT": (-12.0, -56.0), "PA": (-4.0, -52.0), "PB": (-7.0, -36.5), "PE": (-8.5, -37.5),
    "PI": (-7.0, -43.0), "PR": (-24.8, -51.5), "RJ": (-22.2, -42.0), "RN": (-5.8, -36.0),
    "RO": (-11.0, -63.0), "RR": (2.0, -61.0), "RS": (-30.0, -53.0), "SC": (-27.0, -50.5),
    "SE": (-10.5, -37.5), "SP": (-22.5, -48.5), "TO": (-9.5, -48.5),
}
NOMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}


def page(uf, uf_nome, centro):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campo político — {uf_nome} por município</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  html,body {{ margin:0; height:100%; font-family: system-ui, Segoe UI, Arial, sans-serif; }}
  #map {{ position:absolute; top:0; bottom:0; left:0; right:0; }}
  .bar {{ position:absolute; z-index:1000; top:10px; left:52px; background:#fff; padding:8px 12px;
         border-radius:10px; box-shadow:0 1px 6px rgba(0,0,0,.3); font-size:13px; max-width:780px; }}
  .bar h2 {{ margin:0 0 6px; font-size:15px; }}
  .bar .row {{ display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin:3px 0; }}
  select {{ padding:4px; border-radius:6px; border:1px solid #aaa; }}
  .ctl {{ position:absolute; z-index:1000; top:150px; left:52px; width:232px; background:#fff;
         border-radius:10px; box-shadow:0 1px 6px rgba(0,0,0,.3); padding:8px 10px; font-size:12px;
         user-select:none; }}
  .ctl-h {{ font-weight:600; cursor:move; margin-bottom:6px; padding-bottom:5px; border-bottom:1px solid #eee;
           display:flex; justify-content:space-between; align-items:center; }}
  .ctl-h button {{ border:none; background:none; cursor:pointer; font-size:13px; color:#888; }}
  .lg {{ font-size:12px; }}
  .lg i {{ width:14px; height:14px; float:left; margin-right:6px; border:1px solid #999; }}
  .pie {{ margin-top:8px; padding-top:6px; border-top:1px solid #eee; }}
  .st {{ position:absolute; z-index:1000; bottom:26px; left:52px; background:#fff; padding:6px 10px;
        border-radius:10px; box-shadow:0 1px 6px rgba(0,0,0,.3); font-size:12px; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="bar">
  <h2>{uf_nome} — campo político por município</h2>
  <div class="row">
    <label>Cargo <select id="cargo"></select></label>
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
  <div class="ctl-h"><span>Legenda (arraste)</span><button id="ctlHide" type="button" title="Esconder">×</button></div>
  <div class="lg" id="leg"></div>
</div>
<div class="ctl" id="ctl2" style="top:150px; left:355px; width:280px;">
  <div class="ctl-h"><span>Direita × Esquerda (arraste)</span><button id="ctl2Hide" type="button" title="Esconder">×</button></div>
  <div class="pie" id="pie"></div>
</div>
<div class="st" id="st"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const GEO = __GEO__;
const DATA = __DATA__;
const LEGEND = {{
  dir:  [[0,30,'#e8eefd'],[30,45,'#b8cdf8'],[45,55,'#7695ef'],[55,70,'#3a5fd9'],[70,101,'#0028a8']],
  esq:  [[0,30,'#fde8e8'],[30,45,'#f8b8b8'],[45,55,'#ef7676'],[55,70,'#d93a3a'],[70,101,'#a80000']],
  vdir: [[0,2000,'#f2f2f2'],[2000,10000,'#d8e4fd'],[10000,50000,'#7695ef'],[50000,200000,'#3a5fd9'],[200000,2e9,'#0028a8']],
  vesq: [[0,2000,'#f2f2f2'],[2000,10000,'#fdd8d8'],[10000,50000,'#ef7676'],[50000,200000,'#d93a3a'],[200000,2e9,'#a80000']]
}};
const WCOL = {{DIREITA:'#3a5fd9', ESQUERDA:'#d93a3a', CENTRO:'#8a8a8a', EMPATE:'#f2c12e', '':'#ddd'}};

const CENTRO = __CENTRO__;
const map = L.map('map').setView(CENTRO, 8);
let geoLayer = null;

function render() {{
  const cargo = document.getElementById('cargo').value;
  const ano = document.getElementById('ano').value;
  const turno = document.getElementById('turno').value;
  const met = document.getElementById('met').value;
  const dd = ((DATA[cargo] || {{}})[ano] || {{}})[turno] || {{}};
  if (geoLayer) map.removeLayer(geoLayer);
  geoLayer = L.geoJSON(GEO, {{
    style: function (f) {{ return {{
      fillColor: fillColor(f, dd, met), weight: 1, opacity: 1, color: '#fff', fillOpacity: 0.85
    }}; }},
    onEachFeature: function (f, layer) {{
      const d = dd[f.properties.cod];
      const nm = f.properties.nome || f.properties.cod;
      let txt = '<b>' + nm + '</b>';
      if (d) {{
        if (met === 'w') txt += '<br>Campo: <b>' + d.w + '</b>';
        else if (met.indexOf('v') === 0)
          txt += '<br>' + (met === 'vdir' ? 'DIR ' : 'ESQ ') + Number(valFor(f, dd, met)).toLocaleString('pt-BR') +
                 '<br>Válidos ' + Number(d.validos).toLocaleString('pt-BR');
        else
          txt += '<br>' + (met === 'dir' ? 'Direita' : 'Esquerda') + ': <b>' +
                 valFor(f, dd, met).toFixed(1) + '%</b>' +
                 '<br>DIR ' + Number(d.vd).toLocaleString('pt-BR') +
                 ' · ESQ ' + Number(d.ve).toLocaleString('pt-BR');
      }} else {{
        txt += '<br><i>sem dados</i>';
      }}
      layer.bindTooltip(txt, {{ sticky: true }});
    }}
  }}).addTo(map);
  legend(met);
  summary(dd);
}}
function fillColor(f, dd, met) {{
  const d = dd[f.properties.cod];
  if (met === 'w') return WCOL[d ? d.w : ''] || WCOL[''];
  if (!d) return '#ccc';
  const val = met === 'dir' ? d.pd : met === 'esq' ? d.pe : met === 'vdir' ? d.vd : d.ve;
  const bins = LEGEND[met];
  for (let i = 0; i < bins.length; i++) {{
    if (val >= bins[i][0] && val < bins[i][1]) return bins[i][2];
  }}
  return bins[bins.length - 1][2];
}}
function valFor(f, dd, met) {{
  const d = dd[f.properties.cod];
  if (!d) return null;
  if (met === 'dir') return d.pd;
  if (met === 'esq') return d.pe;
  if (met === 'vdir') return d.vd;
  if (met === 'vesq') return d.ve;
  return null;
}}
function legend(met) {{
  const lg = document.getElementById('leg');
  if (met === 'w') {{
    lg.innerHTML = '<b>Vencedor</b><br>' + ['DIREITA','ESQUERDA','CENTRO','EMPATE'].map(function (k) {{
      return '<i style="background:' + WCOL[k] + '"></i>' + k + '<br>';
    }}).join('');
    return;
  }}
  const bins = LEGEND[met];
  lg.innerHTML = '<b>' + (met === 'dir' ? '% Direita' : met === 'esq' ? '% Esquerda' : met === 'vdir' ? 'Votos DIR' : 'Votos ESQ') + '</b><br>' +
    bins.map(function (b) {{
      const hi = b[1] > 1e6 ? 'mais' : Number(b[1]).toLocaleString('pt-BR');
      return '<i style="background:' + b[2] + '"></i>' +
             (met.indexOf('v') === 0 ? Number(b[0]).toLocaleString('pt-BR') + ' – ' + hi : b[0] + ' – ' + hi + '%') + '<br>';
    }}).join('');
}}
function summary(dd) {{
  let n = 0, svd = 0, sve = 0, svc = 0;
  for (const k in dd) {{ n++; const d = dd[k]; svd += d.vd; sve += d.ve; svc += d.vc; }}
  const tot = svd + sve + svc;
  document.getElementById('st').innerHTML =
    (n ? n + ' municípios com dados · ' : '') +
    (tot ? 'DIR ' + svd.toLocaleString('pt-BR') + ' (' + (100 * svd / tot).toFixed(1) + '%) · ESQ ' +
    sve.toLocaleString('pt-BR') + ' (' + (100 * sve / tot).toFixed(1) + '%)' : '');
  renderPie(svd, sve, svc);
}}
function renderPie(svd, sve, svc) {{
  const el = document.getElementById('pie');
  const tot = svd + sve + svc;
  if (!tot) {{ el.innerHTML = '<div style="color:#888">sem dados</div>'; return; }}
  const r = 26, C = 2 * Math.PI * r, W = 13;
  const parts = svc > 0
    ? [{{ c:'#d93a3a', v:sve, n:'Esquerda' }}, {{ c:'#8a8a8a', v:svc, n:'Centro' }}, {{ c:'#3a5fd9', v:svd, n:'Direita' }}]
    : [{{ c:'#d93a3a', v:sve, n:'Esquerda' }}, {{ c:'#3a5fd9', v:svd, n:'Direita' }}];
  let arcs = '', off = 0;
  for (const p of parts) {{
    const frac = p.v / tot;
    arcs += '<circle cx="44" cy="44" r="' + r + '" fill="none" stroke="' + p.c + '" stroke-width="' + W +
            '" stroke-dasharray="' + (frac * C).toFixed(2) + ' ' + C.toFixed(2) +
            '" stroke-dashoffset="' + (-off).toFixed(2) + '" transform="rotate(-90 44 44)"/>';
    off += frac * C;
  }}
  el.innerHTML = '<div style="display:flex;gap:10px;align-items:center">' +
    '<svg width="88" height="88" viewBox="0 0 88 88">' + arcs + '</svg>' +
    '<div>' + parts.map(function (p) {{
      return '<div style="display:flex;align-items:center;margin:3px 0;font-size:12px">' +
        '<i style="width:11px;height:11px;background:' + p.c + ';display:inline-block;margin-right:6px;border-radius:2px"></i>' +
        p.n + ' <b style="margin-left:6px">' + (100 * p.v / tot).toFixed(1) + '%</b></div>';
    }}).join('') + '</div></div>';
}}
(function drag() {{
  function makeCtl(ctlId, hideId, showId) {{
    const ctl = document.getElementById(ctlId);
    let dragging = false, dx = 0, dy = 0;
    ctl.querySelector('.ctl-h').addEventListener('pointerdown', function (e) {{
      dragging = true;
      const r = ctl.getBoundingClientRect();
      dx = e.clientX - r.left; dy = e.clientY - r.top;
      e.preventDefault();
    }});
    window.addEventListener('pointermove', function (e) {{
      if (!dragging) return;
      ctl.style.left = (e.clientX - dx) + 'px';
      ctl.style.top = (e.clientY - dy) + 'px';
    }});
    window.addEventListener('pointerup', function () {{ dragging = false; }});
    document.getElementById(hideId).addEventListener('click', function () {{ ctl.style.display = 'none'; }});
    document.getElementById(showId).addEventListener('click', function () {{ ctl.style.display = 'block'; }});
  }}
  makeCtl('ctl', 'ctlHide', 'tb2');
  makeCtl('ctl2', 'ctl2Hide', 'tb3');
}})();
function fillTurno(cargo, ano) {{
  const turnos = Object.keys((DATA[cargo] || {{}})[ano] || {{}}).sort();
  document.getElementById('turno').innerHTML = turnos.map(function (t) {{
    return '<option value="' + t + '"' + (t === turnos[turnos.length - 1] ? ' selected' : '') + '>Turno ' + t + '</option>';
  }}).join('');
}}
function resizeAno() {{
  const cargo = document.getElementById('cargo').value;
  const anos = Object.keys(DATA[cargo] || {{}}).sort();
  document.getElementById('ano').innerHTML = anos.map(function (a) {{
    return '<option value="' + a + '"' + (a === anos[anos.length - 1] ? ' selected' : '') + '>' + a + '</option>';
  }}).join('');
  fillTurno(cargo, document.getElementById('ano').value);
  render();
}}
document.getElementById('cargo').innerHTML = Object.keys(DATA).map(function (c, i) {{
  return '<option value="' + c + '"' + (i === 0 ? ' selected' : '') + '>' +
         c.split(' ').map(function (w) {{ return w.charAt(0).toUpperCase() + w.slice(1); }}).join(' ') + '</option>';
}}).join('');
document.getElementById('ano').addEventListener('change', function () {{
  fillTurno(document.getElementById('cargo').value, this.value);
  render();
}});
document.getElementById('cargo').addEventListener('change', resizeAno);
document.getElementById('met').addEventListener('change', render);
resizeAno();
</script>
</body>
</html>
"""


def main():
    ufs = [u.upper() for u in sys.argv[1:]] or list(NOMES)

    con = duckdb.connect(DB, read_only=True)
    ibge2tse = {}
    for tse, ibge in con.execute(
        "SELECT cd_municipio_tse, cd_municipio_ibge FROM dim_municipio"
    ).fetchall():
        ibge2tse[str(int(ibge))] = tse
    con.close()

    data_rows = []
    with CSV.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=","):
            data_rows.append(r)

    for uf in ufs:
        if uf not in NOMES:
            print(f"  ! UF desconhecida: {uf}")
            continue
        geojson = GEO_DIR / f"{uf}_municipios.geojson"
        if not geojson.exists():
            print(f"  ! geojson nao existe: {geojson}")
            continue
        geo = json.loads(geojson.read_text(encoding="utf-8"))
        print(f"  {uf}: {len(geo['features'])} municipios no geojson")

        data = {}
        for r in data_rows:
            if r["sg_uf"] != uf:
                continue
            cargo, ano, turno = r["cargo"], r["ano_eletivo"], r["nr_turno"]
            tse = r["cd_municipio_tse"]
            data.setdefault(cargo, {}).setdefault(ano, {}).setdefault(turno, {})[tse] = {
                "vd": int(r["vot_dir"]),
                "ve": int(r["vot_esq"]),
                "vc": int(r["vot_cen"]),
                "validos": int(r["validos"]),
                "pd": float(r["share_dir"]),
                "pe": float(r["share_esq"]),
                "w": r["vencedor_campo"],
            }

        # geojson usa cd_municipio_ibge (7 dig); mapa indexa por cd_municipio_tse
        geo_feats = []
        sem = 0
        for f in geo["features"]:
            code = f["properties"]["cd_municipio_ibge"]
            tse = ibge2tse.get(str(int(code)))
            if tse is None:
                tse = ""
                sem += 1
            geo_feats.append({
                "type": "Feature",
                "properties": {"cod": tse, "nome": f["properties"]["nm_municipio"]},
                "geometry": f["geometry"],
            })
        if sem:
            print(f"     municipios sem dim_municipio: {sem}")
        geo_out = {"type": "FeatureCollection", "features": geo_feats}

        out = str(MAPA_OUT).format(uf=uf)
        html = (page(uf, NOMES[uf], CENTROS[uf])
                .replace("__CENTRO__", json.dumps(CENTROS[uf]))
                .replace("__GEO__", json.dumps(geo_out, ensure_ascii=False))
                .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
        Path(out).write_text(html, encoding="utf-8")
        print(f"  OK: {out} ({Path(out).stat().st_size/1e6:.1f} MB)")

    if ufs and ufs[0] in NOMES:
        webbrowser.open((str(MAPA_OUT)).format(uf=ufs[0]).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())