# -*- coding: utf-8 -*-
"""Gera mapa Leaflet interativo do GOV 2022 (1T) por local de votacao em SP.

Fonte: data/analise/mapa_voto_local_2022.csv (query q17).
Saida: data/analise/mapa_voto_local_2022.html (Leaflet + dados embutidos em JSON).
"""
import csv
import json

CSV_IN = "data/analise/mapa_voto_local_2022.csv"
HTML_OUT = "data/analise/mapa_voto_local_2022.html"

points = []
with open(CSV_IN, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter=";"):
        if not row["lat"] or not row["lon"]:
            continue
        points.append({
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "validos": int(float(row["validos"] or 0)),
            "tarcisio": round(float(row["share_tarcisio"] or 0), 2),
            "haddad": round(float(row["share_haddad"] or 0), 2),
            "mun": row["nm_municipio_tse"].strip().title(),
            "local": row["nm_local_votacao"].strip().title(),
        })

payload = json.dumps(points, ensure_ascii=False, separators=(",", ":"))

html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Governador SP 2022 (1T) - Voto por local de votacao</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body, #map { height: 100%; margin: 0; font-family: Arial, Helvetica, sans-serif; }
  #topo {
    position: absolute; top: 10px; left: 50px; z-index: 1000;
    background: rgba(255,255,255,.95); padding: 10px 14px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25); font-size: 13px; max-width: 340px;
  }
  #topo h1 { margin: 0 0 4px; font-size: 16px; }
  #topo p  { margin: 0 0 8px; color: #555; font-size: 12px; }
  #filtro { font-size: 12px; }
  #filtro input { width: 90px; margin-left: 6px; }
  #legenda {
    position: absolute; bottom: 30px; right: 10px; z-index: 1000;
    background: rgba(255,255,255,.95); padding: 8px 10px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25); font-size: 12px; line-height: 1.5;
  }
  .cor { display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 6px; }
  #resumo {
    position: absolute; bottom: 30px; left: 10px; z-index: 1000;
    background: rgba(255,255,255,.95); padding: 8px 10px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25); font-size: 12px;
  }
  @media print { #topo, #legenda, #resumo { display: none; } }
</style>
</head>
<body>
<div id="map"></div>
<div id="topo">
  <h1>Governador SP 2022 - 1º turno por local de votação</h1>
  <p>7.454 locais · cor = vantagem Tarcísio (azul) x Haddad (vermelho) · raio = votos válidos.</p>
  <div id="filtro">
    <label>Mínimo de votos válidos no local: <input type="range" id="minVotos" min="0" max="5000" step="50" value="100"></label>
    <span id="qtdLocais"></span>
  </div>
</div>
<div id="legenda">
  <strong>Vantagem</strong><br>
  <span class="cor" style="background:#08306b"></span>+60 Tarcísio<br>
  <span class="cor" style="background:#2171b5"></span>+30 Tarcísio<br>
  <span class="cor" style="background:#bdbdbd"></span>Balanço<br>
  <span class="cor" style="background:#cb181d"></span>+30 Haddad<br>
  <span class="cor" style="background:#67000d"></span>+60 Haddad
</div>
<div id="resumo"></div>
<script>
const DATA = __DATA__;

const map = L.map("map").setView([-22.9, -49.2], 7);
const layers = {
  "Carto Positron": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {maxZoom: 19, attribution: "&copy; OSM &copy; CARTO"}),
  "Carto Dark":     L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",   {maxZoom: 19, attribution: "&copy; OSM &copy; CARTO"}),
  "OSM":            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",            {maxZoom: 19, attribution: "&copy; OSM"}),
};
layers["Carto Positron"].addTo(map);
L.control.layers(layers, null, {position: "topright"}).addTo(map);

function corVantagem(diff) {
  if (diff >= 60) return "#08306b";
  if (diff >= 30) return "#2171b5";
  if (diff > 15)  return "#9ecae1";
  if (diff < -60) return "#67000d";
  if (diff < -30) return "#cb181d";
  if (diff < -15) return "#fc9272";
  return "#bdbdbd";
}

function raio(vot) { return 3 + 7 * Math.sqrt(vot / 5000); }

let minimo = 100;
function refresh() {
  map.eachLayer(l => { if (l instanceof L.CircleMarker) map.removeLayer(l); });
  const cluster = L.featureGroup().addTo(map);
  let visiveis = 0, somaV = 0, somaT = 0, ganhou = {t: 0, h: 0};
  for (const p of DATA) {
    if (p.validos < minimo) continue;
    const diff = p.tarcisio - p.haddad;
    const m = L.circleMarker([p.lat, p.lon], {
      radius: raio(p.validos),
      weight: 1, opacity: .6, color: "#333",
      fillColor: corVantagem(diff), fillOpacity: .75,
    }).bindPopup(
      "<b>" + p.local + "</b><br>" + p.mun +
      "<br>V\u00e1lidos: <b>" + p.validos.toLocaleString("pt-BR") + "</b>" +
      "<br>Tarc\u00edsio: <b>" + p.tarcisio.toFixed(1) + "%</b>" +
      "<br>Haddad: <b>" + p.haddad.toFixed(1) + "%</b>" +
      "<br>Vantagem: " + (diff >= 0 ? "+" : "") + diff.toFixed(1) + " pp"
    );
    m.addTo(cluster);
    visiveis++; somaV += p.validos; somaT += diff;
    if (diff > 0) ganhou.t++; else ganhou.h++;
  }
  document.getElementById("qtdLocais").textContent = "(" + visiveis + " locais)";
  document.getElementById("resumo").innerHTML =
    "<strong>" + visiveis + "</strong> locais · <strong>" + (somaV/1000).toFixed(0) + " mil</strong> votos" +
    "<br>Locais p/ Tarcísio: <b style='color:#08306b'>" + ganhou.t + "</b> · p/ Haddad: <b style='color:#67000d'>" + ganhou.h + "</b>";
}

document.getElementById("minVotos").addEventListener("input", e => {
  minimo = +e.target.value;
  document.getElementById("minVotos").title = "Mínimo " + minimo;
  refresh();
});

refresh();
</script>
</body>
</html>
"""

html = html.replace("__DATA__", payload)
with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK: %s (%d pontos, %.2f MB)" % (HTML_OUT, len(points), len(html) / 1024 / 1024))