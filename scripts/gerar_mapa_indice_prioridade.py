# -*- coding: utf-8 -*-
"""Mapa Leaflet do Indice de Prioridade de campanha por local de votacao.

Fonte: data/analise/indice_prioridade_{cargo}_2022.csv (q20/q21/q22).
Saida: data/analise/mapa_indice_prioridade_{cargo}_2022.html

Cor = ACAO recomendada (nao quem venceu - isso ja existe nos outros mapas):
  verde   = Base consolidada (so manter)
  azul    = Mobilizacao (GOTV - ja concorda, falta votar)
  dourado = Persuasao (maior ROI de convencimento)
  laranja = Persuasao + Mobilizacao (prioridade maxima)
  cinza   = Hostil (nao vale investir)
Toggle Direita/Esquerda troca o ponto de vista (quadrante_direita/quadrante_esquerda).
Uso: python gerar_mapa_indice_prioridade.py [cargo]   (default: presidente)
"""
import csv
import json
import sys

CARGO = sys.argv[1] if len(sys.argv) > 1 else "presidente"
TITULOS = {
    "presidente": "Presidente Brasil 2022 (2º turno)",
    "governador": "Governador Brasil 2022 (2º/1º turno)",
    "depfederal": "Deputado Federal Brasil 2022",
}
CSV_IN = f"data/analise/indice_prioridade_{CARGO}_2022.csv"
HTML_OUT = f"data/analise/mapa_indice_prioridade_{CARGO}_2022.html"

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
            "validos": int(num("validos") or 0),
            "shareDir": num("share_dir"),
            "shareEsq": num("share_esq"),
            "abst": num("abstencao_pct"),
            "gap": num("gap_pct_aptos"),
            "qDir": row["quadrante_direita"],
            "qEsq": row["quadrante_esquerda"],
        })

payload = json.dumps(points, ensure_ascii=False, separators=(",", ":"))
titulo = TITULOS.get(CARGO, CARGO)

html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indice de Prioridade - __TITULO__</title>
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
    box-shadow: 0 2px 8px rgba(0,0,0,.25); font-size: 13px; max-width: 360px;
  }
  #topo h1 { margin: 0 0 4px; font-size: 15px; }
  #topo p  { margin: 0 0 8px; color: #555; font-size: 12px; }
  .toggle { display:flex; gap:4px; margin-bottom:6px; }
  .toggle button {
    flex:1; padding:6px 8px; border:1px solid #ccc; background:#f2f2f2; cursor:pointer;
    font-size:12px; border-radius:6px;
  }
  .toggle button.ativo { background:#263238; color:#fff; border-color:#263238; }
  #filtro { font-size: 12px; }
  #filtro input { width: 90px; margin-left: 6px; }
  #legenda {
    position: absolute; bottom: 30px; right: 10px; z-index: 1000;
    background: rgba(255,255,255,.95); padding: 10px 12px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,.25); font-size: 12px; line-height: 1.7;
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
  <h1>Indice de Prioridade - __TITULO__</h1>
  <p>Cor = acao recomendada por local (nao quem venceu) · raio = votos validos.</p>
  <div class="toggle">
    <button id="btnDir" class="ativo">Ver como DIREITA</button>
    <button id="btnEsq">Ver como ESQUERDA</button>
  </div>
  <div id="filtro">
    <label>Mínimo de votos válidos no local: <input type="range" id="minVotos" min="0" max="5000" step="50" value="100"></label>
    <span id="qtdLocais"></span>
  </div>
</div>
<div id="legenda">
  <strong>Prioridade de campanha</strong><br>
  <span class="cor" style="background:#2e7d32"></span>Base consolidada (manter)<br>
  <span class="cor" style="background:#0277bd"></span>Mobilizacao (GOTV)<br>
  <span class="cor" style="background:#f9a825"></span>Persuasao (maior ROI)<br>
  <span class="cor" style="background:#e65100"></span>Persuasao + Mobilizacao<br>
  <span class="cor" style="background:#9e9e9e"></span>Hostil (nao vale)
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
  BASE_CONSOLIDADA: "#2e7d32",
  MOBILIZACAO: "#0277bd",
  PERSUASAO: "#f9a825",
  PERSUASAO_MOBILIZACAO: "#e65100",
  HOSTIL: "#9e9e9e",
};
const NOMES = {
  BASE_CONSOLIDADA: "Base consolidada",
  MOBILIZACAO: "Mobilizacao (GOTV)",
  PERSUASAO: "Persuasao",
  PERSUASAO_MOBILIZACAO: "Persuasao + Mobilizacao",
  HOSTIL: "Hostil",
};

function raio(vot) { return 3 + 7 * Math.sqrt(vot / 5000); }

let minimo = 100;
let lado = "qDir"; // ou "qEsq"
let cluster = L.markerClusterGroup({ maxClusterRadius: 50, disableClusteringAtZoom: 15 }).addTo(map);

function refresh() {
  cluster.clearLayers();
  let visiveis = 0, somaV = 0;
  const contagem = {};
  for (const p of DATA) {
    if (p.validos < minimo) continue;
    const q = p[lado];
    const cor = CORES[q] || "#ccc";
    contagem[q] = (contagem[q] || 0) + 1;
    const m = L.circleMarker([p.lat, p.lon], {
      radius: raio(p.validos),
      weight: 1, opacity: .6, color: "#333",
      fillColor: cor, fillOpacity: .8,
    }).bindPopup(
      "<b>" + p.local + "</b><br>" + p.mun +
      "<br>Válidos: <b>" + p.validos.toLocaleString("pt-BR") + "</b>" +
      "<br>Direita: <b>" + (p.shareDir ?? "-") + "%</b> · Esquerda: <b>" + (p.shareEsq ?? "-") + "%</b>" +
      "<br>Abstenção: " + (p.abst ?? "sem dado") + (p.abst != null ? "%" : "") +
      "<br>Gap p/ virar: " + p.gap + "% dos aptos" +
      "<br><b style='color:" + cor + "'>" + (NOMES[q] || q) + "</b>"
    );
    m.addTo(cluster);
    visiveis++; somaV += p.validos;
  }
  document.getElementById("qtdLocais").textContent = "(" + visiveis + " locais)";
  let resumoHtml = "<strong>" + visiveis + "</strong> locais · <strong>" + (somaV/1000).toFixed(0) + " mil</strong> votos<br>";
  for (const k of Object.keys(NOMES)) {
    resumoHtml += "<span style='color:" + CORES[k] + "'>" + (contagem[k]||0) + "</span> " + NOMES[k] + "<br>";
  }
  document.getElementById("resumo").innerHTML = resumoHtml;
}

document.getElementById("minVotos").addEventListener("input", e => {
  minimo = +e.target.value;
  document.getElementById("minVotos").title = "Mínimo " + minimo;
  refresh();
});
document.getElementById("btnDir").addEventListener("click", () => {
  lado = "qDir";
  document.getElementById("btnDir").classList.add("ativo");
  document.getElementById("btnEsq").classList.remove("ativo");
  refresh();
});
document.getElementById("btnEsq").addEventListener("click", () => {
  lado = "qEsq";
  document.getElementById("btnEsq").classList.add("ativo");
  document.getElementById("btnDir").classList.remove("ativo");
  refresh();
});

refresh();
</script>
</body>
</html>
"""

html = html.replace("__DATA__", payload).replace("__TITULO__", titulo)
with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK: %s (%d pontos, %.2f MB)" % (HTML_OUT, len(points), len(html) / 1024 / 1024))
