# -*- coding: utf-8 -*-
"""Grafico de dispersao (scatter) com regressao - Voto x Indicador socioeconomico.

Fonte: data/analise/voto_x_indicadores_municipio_2022.csv (q25).
Saida: data/analise/grafico_correlacao.html

Cada ponto = 1 municipio de SP. Eixo X = indicador socioeconomico (escolha),
eixo Y = % de voto por campo (escolha). Regressao linear + R² calculados no
proprio navegador (minimos quadrados simples), pra permitir trocar os eixos
sem reprocessar nada no servidor.
Uso: python gerar_grafico_correlacao.py
"""
import csv
import json

CSV_IN = "data/analise/voto_x_indicadores_municipio_2022.csv"
HTML_OUT = "data/analise/grafico_correlacao.html"

points = []
with open(CSV_IN, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter=";"):
        def num(c):
            v = row.get(c, "")
            return float(v) if v not in (None, "") else None
        points.append({
            "mun": row["nm_municipio_tse"].strip().title(),
            "pop": num("ibge_pop_2022"),
            "dens": num("dens_hab_km2"),
            "pib_pc": num("ibge_pib_pc_2023"),
            "idhm": num("ibge_idhm_2010"),
            "idhm_edu": num("ibge_idhm_educacao_2010"),
            "idhm_renda": num("ibge_idhm_renda_2010"),
            "pres_dir": num("pres_dir"),
            "pres_esq": num("pres_esq"),
            "dep_dir": num("dep_dir"),
            "dep_cen": num("dep_cen"),
            "dep_esq": num("dep_esq"),
        })

payload = json.dumps(points, ensure_ascii=False, separators=(",", ":"))

html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Correlação: Voto x Indicadores - SP</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js"></script>
<style>
  body { font-family: Arial, Helvetica, sans-serif; margin: 0; padding: 20px; background: #f4f8fc; color: #11233b; }
  .wrap { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 4px; color: #061a38; }
  p.sub { color: #5b6b80; font-size: 13px; margin: 0 0 18px; }
  .controles { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
  .controles label { font-size: 13px; font-weight: 700; display: flex; flex-direction: column; gap: 4px; }
  .controles select { font-size: 14px; padding: 7px 10px; border-radius: 8px; border: 1px solid #dce5ef; }
  .card { background: #fff; border: 1px solid #dce5ef; border-radius: 14px; padding: 18px; box-shadow: 0 8px 20px rgba(22,57,92,.06); }
  #stats { font-size: 13px; color: #11233b; margin-bottom: 10px; padding: 10px 14px; background: #f4f8fc; border-radius: 8px; }
  #stats b { color: #087ee6; }
  canvas { max-height: 480px; }
  .aviso { font-size: 11.5px; color: #8494a8; margin-top: 18px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Voto x Indicadores socioeconômicos — municípios de SP</h1>
  <p class="sub">Cada ponto é um dos 645 municípios de SP (eleição 2022). Regressão linear calculada em tempo real.</p>
  <div class="controles">
    <label>Eixo X (indicador):
      <select id="selX">
        <option value="idhm">IDHM (2010)</option>
        <option value="idhm_edu">IDHM Educação (2010)</option>
        <option value="idhm_renda">IDHM Renda (2010)</option>
        <option value="pib_pc">PIB per capita (R$, 2023)</option>
        <option value="dens">Densidade (hab/km²)</option>
      </select>
    </label>
    <label>Eixo Y (% de voto):
      <select id="selY">
        <option value="pres_dir">Presidente — Direita (2T)</option>
        <option value="pres_esq">Presidente — Esquerda (2T)</option>
        <option value="dep_dir">Dep. Federal — Direita</option>
        <option value="dep_cen">Dep. Federal — Centro</option>
        <option value="dep_esq">Dep. Federal — Esquerda</option>
      </select>
    </label>
  </div>
  <div class="card">
    <div id="stats"></div>
    <canvas id="chart"></canvas>
  </div>
  <p class="aviso">Fonte: TSE + IBGE (Censo 2022, PIB 2023, IDHM 2010 - Atlas PNUD). Correlação não implica causalidade;
    outros fatores (histórico político local, migração, religião) também influenciam o resultado.</p>
</div>
<script>
const DATA = __DATA__;
const NOMES = {
  idhm: "IDHM (2010)", idhm_edu: "IDHM Educação", idhm_renda: "IDHM Renda",
  pib_pc: "PIB per capita (R$)", dens: "Densidade (hab/km²)",
  pres_dir: "Presidente - Direita", pres_esq: "Presidente - Esquerda",
  dep_dir: "Dep.Federal - Direita", dep_cen: "Dep.Federal - Centro", dep_esq: "Dep.Federal - Esquerda",
};

function regressao(pontos) {
  const n = pontos.length;
  const sx = pontos.reduce((s,p)=>s+p.x,0), sy = pontos.reduce((s,p)=>s+p.y,0);
  const sxy = pontos.reduce((s,p)=>s+p.x*p.y,0), sxx = pontos.reduce((s,p)=>s+p.x*p.x,0);
  const b = (n*sxy - sx*sy) / (n*sxx - sx*sx);
  const a = (sy - b*sx) / n;
  const my = sy/n;
  const ssTot = pontos.reduce((s,p)=>s+(p.y-my)**2,0);
  const ssRes = pontos.reduce((s,p)=>s+(p.y-(a+b*p.x))**2,0);
  const r2 = 1 - ssRes/ssTot;
  return {a, b, r2};
}

let chart;
function render() {
  const kx = document.getElementById("selX").value, ky = document.getElementById("selY").value;
  const pontos = DATA.filter(p => p[kx]!=null && p[ky]!=null).map(p => ({x: p[kx], y: p[ky], mun: p.mun}));
  const reg = regressao(pontos);
  const minX = Math.min(...pontos.map(p=>p.x)), maxX = Math.max(...pontos.map(p=>p.x));
  const linha = [{x:minX, y:reg.a+reg.b*minX}, {x:maxX, y:reg.a+reg.b*maxX}];
  const r = Math.sign(reg.b) * Math.sqrt(Math.max(reg.r2,0));

  const ctx = document.getElementById("chart").getContext("2d");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "scatter",
    data: { datasets: [
      { label: "Municípios", data: pontos, backgroundColor: "rgba(8,126,230,.55)", pointRadius: 4 },
      { label: "Regressão linear", data: linha, type: "line", borderColor: "#a50f15", borderWidth: 2, pointRadius: 0, fill: false }
    ]},
    options: {
      responsive: true,
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { label: c => c.raw.mun ? c.raw.mun + ": (" + c.raw.x.toFixed(2) + ", " + c.raw.y.toFixed(2) + ")" : "" } }
      },
      scales: {
        x: { title: { display: true, text: NOMES[kx] } },
        y: { title: { display: true, text: "% " + NOMES[ky] } }
      }
    }
  });
  document.getElementById("stats").innerHTML =
    "Correlação (r): <b>" + r.toFixed(3) + "</b> · R²: <b>" + reg.r2.toFixed(3) + "</b> · " +
    pontos.length + " municípios · " +
    (Math.abs(r) < .3 ? "correlação fraca" : Math.abs(r) < .6 ? "correlação moderada" : "correlação forte");
}

document.getElementById("selX").addEventListener("change", render);
document.getElementById("selY").addEventListener("change", render);
render();
</script>
</body>
</html>
"""

html = html.replace("__DATA__", payload)
with open(HTML_OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK: %s (%d municipios, %.2f MB)" % (HTML_OUT, len(points), len(html) / 1024 / 1024))
