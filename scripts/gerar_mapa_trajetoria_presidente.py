# -*- coding: utf-8 -*-
"""Mapa Leaflet da Trajetoria de Voto (Presidente 2014->2018->2022) por perfil.

Fonte: data/analise/trajetoria_presidente_2014_2022.csv (q24).
Saida: data/analise/mapa_trajetoria_presidente_2014_2022.html

Cada local colorido pelo seu PERFIL de trajetoria (mapa de pontos com cluster).
NOTA: chegou a existir um modo "rede" (hub geografico + linha ate cada membro do
perfil), removido em 2026-09-29 - com milhares de locais por perfil em escala
Brasil (ex. 7.077 no grupo "Moveu forte p/ Direita") a rede virava uma bola de
linha ilegivel, mesmo mostrando 1 perfil por vez. Decisao do dono: so pontos.
Uso: python gerar_mapa_trajetoria_presidente.py
"""
import csv
import json

CSV_IN = "data/analise/trajetoria_presidente_2014_2022.csv"
HTML_OUT = "data/analise/mapa_trajetoria_presidente_2014_2022.html"

points = []
with open(CSV_IN, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter=";"):
        if not row["lat"] or not row["lon"]:
            continue

        def num(campo):
            v = row.get(campo, "")
            return float(v) if v not in (None, "") else None

        points.append({
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "mun": row["nm_municipio_tse"].strip().title(),
            "local": (row["nm_local_votacao"] or "").strip().title(),
            "validos": int(num("validos_22") or 0),
            "sh14": num("shdir_14"),
            "sh18": num("shdir_18"),
            "sh22": num("shdir_22"),
            "swing1": num("swing1"),
            "swing2": num("swing2"),
            "total": num("total"),
            "perfil": row["perfil"],
        })

payload = json.dumps(points, ensure_ascii=False, separators=(",", ":"))

html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trajetória de Voto - Presidente 2014-2022</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<style>
  html, body, #map { height: 100%; margin: 0; font-family: Arial, Helvetica, sans-serif; }
  #topo {
    position: absolute; top: 10px; left: 50px; z-index: 1000;
    background: rgba(255,255,255,.95); padding: 10px 14px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25); font-size: 13px; max-width: 380px;
  }
  #topo h1 { margin: 0 0 4px; font-size: 15px; }
  #topo p  { margin: 0 0 8px; color: #555; font-size: 12px; }
  #legenda {
    position: absolute; bottom: 30px; right: 10px; z-index: 1000;
    background: rgba(255,255,255,.95); padding: 10px 12px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25); font-size: 12px; line-height: 1.7; max-width: 260px;
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
  <h1>Trajetória de Voto - Presidente 2014→2018→2022</h1>
  <p>Perfil de mudança do share de direita por local, 2014→2022 (só locais presentes
     nos 3 anos, mesmo prédio ao longo do tempo).</p>
</div>
<div id="legenda">
  <strong>Perfil</strong><br>
  <span class="cor" style="background:#08306b"></span>Moveu forte p/ Direita<br>
  <span class="cor" style="background:#4292c6"></span>Moveu moderado p/ Direita<br>
  <span class="cor" style="background:#9ecae1"></span>Estável Direita<br>
  <span class="cor" style="background:#fcae91"></span>Estável Esquerda<br>
  <span class="cor" style="background:#ef3b2c"></span>Moveu moderado p/ Esquerda<br>
  <span class="cor" style="background:#67000d"></span>Moveu forte p/ Esquerda<br>
  <span class="cor" style="background:#6a1b9a"></span>Oscilou (foi e voltou)
</div>
<div id="resumo"></div>
<script>
const DATA = __DATA__;

const map = L.map("map").setView([-14.2, -51.9], 4);
const layers = {
  "Carto Positron": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", {maxZoom: 19, attribution: "&copy; OSM &copy; CARTO"}),
  "Carto Dark":     L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",   {maxZoom: 19, attribution: "&copy; OSM &copy; CARTO"}),
};
layers["Carto Positron"].addTo(map);
L.control.layers(layers, null, {position: "topright"}).addTo(map);

const CORES = {
  MOVEU_FORTE_DIREITA: "#08306b",
  MOVEU_MOD_DIREITA: "#4292c6",
  ESTAVEL_DIREITA: "#9ecae1",
  ESTAVEL_ESQUERDA: "#fcae91",
  MOVEU_MOD_ESQUERDA: "#ef3b2c",
  MOVEU_FORTE_ESQUERDA: "#67000d",
  OSCILOU: "#6a1b9a",
};
const NOMES = {
  MOVEU_FORTE_DIREITA: "Moveu forte p/ Direita",
  MOVEU_MOD_DIREITA: "Moveu moderado p/ Direita",
  ESTAVEL_DIREITA: "Estável Direita",
  ESTAVEL_ESQUERDA: "Estável Esquerda",
  MOVEU_MOD_ESQUERDA: "Moveu moderado p/ Esquerda",
  MOVEU_FORTE_ESQUERDA: "Moveu forte p/ Esquerda",
  OSCILOU: "Oscilou (foi e voltou)",
};

const pontosLayer = L.markerClusterGroup({ maxClusterRadius: 50, disableClusteringAtZoom: 15 }).addTo(map);

function raio(vot) { return 3 + 6 * Math.sqrt((vot||500) / 5000); }

function desenhaPontos() {
  pontosLayer.clearLayers();
  const contagem = {};
  for (const p of DATA) {
    contagem[p.perfil] = (contagem[p.perfil] || 0) + 1;
    L.circleMarker([p.lat, p.lon], {
      radius: raio(p.validos), weight: .5, opacity: .5, color: "#333",
      fillColor: CORES[p.perfil] || "#ccc", fillOpacity: .7,
    }).bindPopup(
      "<b>" + p.local + "</b><br>" + p.mun +
      "<br>Direita 2014: <b>" + p.sh14 + "%</b> → 2018: <b>" + p.sh18 + "%</b> → 2022: <b>" + p.sh22 + "%</b>" +
      "<br>Variação total: " + (p.total>=0?"+":"") + p.total + " pp" +
      "<br><b style='color:" + (CORES[p.perfil]||'#333') + "'>" + (NOMES[p.perfil]||p.perfil) + "</b>"
    ).addTo(pontosLayer);
  }
  let html = "<strong>" + DATA.length + "</strong> locais (2014→2022)<br>";
  for (const k of Object.keys(NOMES)) html += "<span style='color:" + CORES[k] + "'>" + (contagem[k]||0) + "</span> " + NOMES[k] + "<br>";
  document.getElementById("resumo").innerHTML = html;
}

desenhaPontos();
</script>
</body>
</html>
"""

html = html.replace("__DATA__", payload)
with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK: %s (%d pontos, %.2f MB)" % (HTML_OUT, len(points), len(html) / 1024 / 1024))
