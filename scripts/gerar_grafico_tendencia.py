# -*- coding: utf-8 -*-
"""Grafico de linha (tendencia) por cidade e visao geral SP - Presidente e Dep.Federal.

Fonte: data/analise/campo_{presidente,depfederal}_{2014,2018,2022}_por_municipio.csv
       (ja existiam, gerar_campo_presidente.py / gerar_campo_deputado_federal.py).
Saida: data/analise/grafico_tendencia.html

Substitui a tentativa de "grafo" de trajetoria (achou pouco legivel/util) por um
grafico de linha classico: eixo X = eleicao (2014/2018/2022), eixo Y = % de voto,
com selecao de cidade (datalist com busca) ou visao geral do estado.
Presidente usa 2º turno (binario DIR x ESQ); Dep.Federal usa unico turno (DIR/CEN/ESQ).
Uso: python gerar_grafico_tendencia.py
"""
import csv
import json

AN0S = [2014, 2018, 2022]
ANALISE = "data/analise"


def ler(cargo, ano, turno):
    path = f"{ANALISE}/campo_{cargo}_{ano}_por_municipio.csv"
    rows = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if int(r["nr_turno"]) != turno:
                continue
            rows[r["cd_municipio_tse"]] = {
                "nome": r["nm_municipio_tse"],
                "esq": float(r["share_esq"]) if r["share_esq"] else None,
                "cen": float(r["share_cen"]) if r["share_cen"] else None,
                "dir": float(r["share_dir"]) if r["share_dir"] else None,
                "validos": int(float(r["validos"])) if r["validos"] else 0,
                "vot_esq": int(float(r["vot_esq"])) if r["vot_esq"] else 0,
                "vot_cen": int(float(r["vot_cen"] or 0)),
                "vot_dir": int(float(r["vot_dir"])) if r["vot_dir"] else 0,
                "vencedor": r["vencedor_campo"],
            }
    return rows


municipios = {}  # cd -> nome
series = {}      # cd -> {cargo: {ano: {...}}}
totais = {"presidente": {}, "depfederal": {}}  # SP inteiro, recalculado dos votos

for cargo, turno in (("presidente", 2), ("depfederal", 1)):
    for ano in AN0S:
        dados = ler(cargo, ano, turno)
        sv_e = sv_c = sv_d = sv_val = 0
        for cd, d in dados.items():
            municipios[cd] = d["nome"]
            series.setdefault(cd, {}).setdefault(cargo, {})[ano] = d
            sv_e += d["vot_esq"]; sv_c += d["vot_cen"]; sv_d += d["vot_dir"]; sv_val += d["validos"]
        totais[cargo][ano] = {
            "esq": round(100 * sv_e / sv_val, 2) if sv_val else None,
            "cen": round(100 * sv_c / sv_val, 2) if sv_val else None,
            "dir": round(100 * sv_d / sv_val, 2) if sv_val else None,
            "validos": sv_val,
        }

municipios_list = sorted(municipios.items(), key=lambda kv: kv[1])
payload = json.dumps({
    "anos": AN0S,
    "municipios": [{"cd": cd, "nome": nome} for cd, nome in municipios_list],
    "series": series,
    "sp": totais,
}, ensure_ascii=False, separators=(",", ":"))

html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tendência de Voto por Cidade - Brasil</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js"></script>
<style>
  body { font-family: Arial, Helvetica, sans-serif; margin: 0; padding: 20px; background: #f4f8fc; color: #11233b; }
  .wrap { max-width: 980px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 4px; color: #061a38; }
  p.sub { color: #5b6b80; font-size: 13px; margin: 0 0 18px; }
  .controles { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 18px; }
  .controles label { font-size: 13px; font-weight: 600; }
  .controles input, .controles select { font-size: 14px; padding: 7px 10px; border-radius: 8px; border: 1px solid #dce5ef; min-width: 260px; }
  .btnSP { background: #061a38; color: #fff; border: none; padding: 8px 14px; border-radius: 8px; font-weight: 700; cursor: pointer; font-size: 13px; }
  .card { background: #fff; border: 1px solid #dce5ef; border-radius: 14px; padding: 18px; margin-bottom: 18px; box-shadow: 0 8px 20px rgba(22,57,92,.06); }
  .card h2 { font-size: 15px; margin: 0 0 4px; color: #061a38; }
  .card .info { font-size: 12px; color: #5b6b80; margin-bottom: 10px; }
  canvas { max-height: 320px; }
  .aviso { font-size: 11.5px; color: #8494a8; margin-top: 24px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Tendência de voto por cidade — Brasil</h1>
  <p class="sub">Presidente (2º turno) e Deputado Federal, 2014 → 2018 → 2022, por % de votos válidos.</p>
  <div class="controles">
    <label>Cidade: <input list="listaMun" id="buscaMun" placeholder="Digite o nome da cidade..."></label>
    <datalist id="listaMun"></datalist>
    <button class="btnSP" id="btnSP">Ver Brasil (país inteiro)</button>
  </div>
  <div class="card">
    <h2 id="tituloPres">Presidente — Brasil</h2>
    <div class="info" id="infoPres"></div>
    <canvas id="chartPres"></canvas>
  </div>
  <div class="card">
    <h2 id="tituloDep">Deputado Federal — Brasil</h2>
    <div class="info" id="infoDep"></div>
    <canvas id="chartDep"></canvas>
  </div>
  <p class="aviso">Fonte: TSE. Presidente: 2º turno (binário Direita x Esquerda). Deputado Federal: turno único,
    proporcional (Direita/Centro/Esquerda). Municípios que não existiam ou mudaram de código entre eleições
    podem não aparecer em algum ano.</p>
</div>
<script>
const DATA = __DATA__;
const mapaCd = {};
DATA.municipios.forEach(m => mapaCd[m.nome.toLowerCase()] = m.cd);

const lista = document.getElementById("listaMun");
DATA.municipios.forEach(m => {
  const o = document.createElement("option");
  o.value = m.nome;
  lista.appendChild(o);
});

let chartPres, chartDep;

function dsLine(label, color, data) {
  return { label, data, borderColor: color, backgroundColor: color, tension: .25, spanGaps: true, pointRadius: 4 };
}

function render(cargo, canvasId, tituloId, infoId, tituloBase, serieObj, corMap) {
  const anos = DATA.anos;
  const chaves = cargo === "presidente" ? ["dir", "esq"] : ["dir", "cen", "esq"];
  const nomes = { dir: "Direita", cen: "Centro", esq: "Esquerda" };
  const datasets = chaves.map(k => dsLine(nomes[k], corMap[k], anos.map(a => (serieObj[a] || {})[k])));
  const ctx = document.getElementById(canvasId).getContext("2d");
  const existing = canvasId === "chartPres" ? chartPres : chartDep;
  if (existing) existing.destroy();
  const chart = new Chart(ctx, {
    type: "line",
    data: { labels: anos, datasets },
    options: {
      responsive: true,
      scales: { y: { min: 0, max: 100, title: { display: true, text: "% dos votos válidos" } } },
      plugins: { legend: { position: "bottom" } }
    }
  });
  if (canvasId === "chartPres") chartPres = chart; else chartDep = chart;
  document.getElementById(tituloId).textContent = tituloBase;
}

const CORES = { dir: "#08519c", cen: "#8a8a8a", esq: "#a50f15" };

function mostrarSP() {
  render("presidente", "chartPres", "tituloPres", "infoPres", "Presidente — Brasil", DATA.sp.presidente, CORES);
  render("depfederal", "chartDep", "tituloDep", "infoDep", "Deputado Federal — Brasil", DATA.sp.depfederal, CORES);
  const vPres = DATA.anos.map(a => (DATA.sp.presidente[a]||{}).validos||0);
  document.getElementById("infoPres").textContent = "Válidos por ano: " + DATA.anos.map((a,i)=>a+": "+vPres[i].toLocaleString("pt-BR")).join(" · ");
  const vDep = DATA.anos.map(a => (DATA.sp.depfederal[a]||{}).validos||0);
  document.getElementById("infoDep").textContent = "Válidos por ano: " + DATA.anos.map((a,i)=>a+": "+vDep[i].toLocaleString("pt-BR")).join(" · ");
}

function mostrarMunicipio(nome) {
  const cd = mapaCd[nome.toLowerCase().trim()];
  if (!cd) return;
  const s = DATA.series[cd] || {};
  const pres = s.presidente || {};
  const dep = s.depfederal || {};
  render("presidente", "chartPres", "tituloPres", "infoPres", "Presidente — " + nome, pres, CORES);
  render("depfederal", "chartDep", "tituloDep", "infoDep", "Deputado Federal — " + nome, dep, CORES);
  const venc = DATA.anos.map(a => (pres[a]||{}).vencedor || "-").join(" → ");
  document.getElementById("infoPres").textContent = "Vencedor por ano: " + venc;
  const vencD = DATA.anos.map(a => (dep[a]||{}).vencedor || "-").join(" → ");
  document.getElementById("infoDep").textContent = "Vencedor por ano: " + vencD;
}

document.getElementById("btnSP").addEventListener("click", mostrarSP);
document.getElementById("buscaMun").addEventListener("change", e => mostrarMunicipio(e.target.value));

mostrarSP();
</script>
</body>
</html>
"""

html = html.replace("__DATA__", payload)
with open(f"{ANALISE}/grafico_tendencia.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"OK: {ANALISE}/grafico_tendencia.html ({len(municipios)} municipios, {len(html)/1024/1024:.2f} MB)")
