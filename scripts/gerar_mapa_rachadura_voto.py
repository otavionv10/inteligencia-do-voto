# -*- coding: utf-8 -*-
"""Mapa Leaflet da "Rachadura de Voto" (ticket-splitting) por local - SP 2022.

Fonte: data/analise/rachadura_voto_2022.csv (q23).
Saida: data/analise/mapa_rachadura_voto_2022.html

Cor = categoria de consistencia entre Presidente/Governador/Dep.Federal:
  azul escuro   = Consistente Direita (os 3 cargos concordam)
  azul claro    = Fragmentacao Direita (voto de direita se espalhou entre
                  candidatos a dep.federal, mas ainda maior que a esquerda ali)
  vermelho esc. = Consistente Esquerda
  vermelho claro= Fragmentacao Esquerda
  laranja       = Rachado Legislativo (o lado OPOSTO tem mais força no
                  Dep.Federal do que no Executivo - divergencia real)
  roxo          = Rachado Executivo (Presidente x Governador com vencedores
                  DIFERENTES - o sinal mais forte e mais raro de persuasao)
Uso: python gerar_mapa_rachadura_voto.py
"""
import csv
import json

CSV_IN = "data/analise/rachadura_voto_2022.csv"
HTML_OUT = "data/analise/mapa_rachadura_voto_2022.html"

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
            "validos": int(num("validos_pres") or 0),
            "shDirPres": num("shdir_pres"),
            "shDirGov": num("shdir_gov"),
            "shDirDep": num("shdir_depfed"),
            "shEsqDep": num("shesq_depfed"),
            "vencPres": row["venc_pres"],
            "vencGov": row["venc_gov"],
            "vencDep": row["venc_depfed"],
            "dissonancia": num("dissonancia_pct"),
            "cat": row["categoria"],
        })

payload = json.dumps(points, ensure_ascii=False, separators=(",", ":"))

html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rachadura de Voto - Brasil 2022</title>
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
  #filtro { font-size: 12px; }
  #filtro input { width: 90px; margin-left: 6px; }
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
  <h1>Rachadura de Voto - Brasil 2022</h1>
  <p>Onde Presidente/Governador/Dep.Federal concordam ou divergem, por local · raio = votos válidos.</p>
  <div id="filtro">
    <label>Mínimo de votos válidos no local: <input type="range" id="minVotos" min="0" max="5000" step="50" value="100"></label>
    <span id="qtdLocais"></span>
  </div>
</div>
<div id="legenda">
  <strong>Categoria</strong><br>
  <span class="cor" style="background:#6a1b9a"></span>Rachado Executivo (Pres. ≠ Gov.)<br>
  <span class="cor" style="background:#f9a825"></span>Rachado Legislativo (oposto vence no Dep.Fed)<br>
  <span class="cor" style="background:#08306b"></span>Consistente Direita<br>
  <span class="cor" style="background:#6baed6"></span>Fragmentação Direita<br>
  <span class="cor" style="background:#67000d"></span>Consistente Esquerda<br>
  <span class="cor" style="background:#fc9272"></span>Fragmentação Esquerda
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
  RACHADO_EXECUTIVO: "#6a1b9a",
  RACHADO_LEGISLATIVO: "#f9a825",
  CONSISTENTE_DIREITA: "#08306b",
  FRAGMENTACAO_DIREITA: "#6baed6",
  CONSISTENTE_ESQUERDA: "#67000d",
  FRAGMENTACAO_ESQUERDA: "#fc9272",
};
const NOMES = {
  RACHADO_EXECUTIVO: "Rachado Executivo",
  RACHADO_LEGISLATIVO: "Rachado Legislativo",
  CONSISTENTE_DIREITA: "Consistente Direita",
  FRAGMENTACAO_DIREITA: "Fragmentação Direita",
  CONSISTENTE_ESQUERDA: "Consistente Esquerda",
  FRAGMENTACAO_ESQUERDA: "Fragmentação Esquerda",
};
// desenha os "raros" (rachado) por cima dos comuns (consistente/fragmentacao)
const ORDEM_Z = ["CONSISTENTE_DIREITA","CONSISTENTE_ESQUERDA","FRAGMENTACAO_DIREITA",
                  "FRAGMENTACAO_ESQUERDA","RACHADO_LEGISLATIVO","RACHADO_EXECUTIVO"];

function raio(vot) { return 3 + 7 * Math.sqrt(vot / 5000); }

let minimo = 100;
let cluster = L.markerClusterGroup({ maxClusterRadius: 50, disableClusteringAtZoom: 15 }).addTo(map);
function refresh() {
  cluster.clearLayers();
  let visiveis = 0, somaV = 0;
  const contagem = {};
  const porOrdem = ORDEM_Z.flatMap(cat => DATA.filter(p => p.cat === cat));
  for (const p of porOrdem) {
    if (p.validos < minimo) continue;
    const cor = CORES[p.cat] || "#ccc";
    contagem[p.cat] = (contagem[p.cat] || 0) + 1;
    const m = L.circleMarker([p.lat, p.lon], {
      radius: raio(p.validos),
      weight: 1, opacity: .6, color: "#333",
      fillColor: cor, fillOpacity: .8,
    }).bindPopup(
      "<b>" + p.local + "</b><br>" + p.mun +
      "<br>Válidos (Presidente): <b>" + p.validos.toLocaleString("pt-BR") + "</b>" +
      "<br>Presidente: <b>" + p.vencPres + "</b> (" + p.shDirPres + "% dir)" +
      "<br>Governador: <b>" + p.vencGov + "</b> (" + p.shDirGov + "% dir)" +
      "<br>Dep.Federal: <b>" + p.vencDep + "</b> (" + p.shDirDep + "% dir / " + p.shEsqDep + "% esq)" +
      "<br>Dissonância: " + p.dissonancia + " pp" +
      "<br><b style='color:" + cor + "'>" + (NOMES[p.cat] || p.cat) + "</b>"
    );
    m.addTo(cluster);
    visiveis++; somaV += p.validos;
  }
  document.getElementById("qtdLocais").textContent = "(" + visiveis + " locais)";
  let resumoHtml = "<strong>" + visiveis + "</strong> locais · <strong>" + (somaV/1000).toFixed(0) + " mil</strong> votos<br>";
  for (const k of ORDEM_Z) {
    resumoHtml += "<span style='color:" + CORES[k] + "'>" + (contagem[k]||0) + "</span> " + NOMES[k] + "<br>";
  }
  document.getElementById("resumo").innerHTML = resumoHtml;
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
