#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_mapa_zonas.py
FUNCAO    : Mapa de calor das ZONAS eleitorais de SP (Leaflet, autossuficiente).
            Cada zona vira um circulo no seu centroide, cor por % DIREITA
            (divergente vermelho<->azul) e raio ~ votos validos. Alterna cargo
            (Presidente 2T / Deputado Federal 1T) e metrica (% Direita/Esquerda).
FONTE     : data/analise/ranking_zonas_{slug}_2022_{t}t.csv (de gerar_ranking_zonas.py)
SAIDA     : data/analise/mapa_calor_zonas.html
USO       : python _scripts/gerar_mapa_zonas.py
"""
import csv
import json
import sys
from pathlib import Path

ANALISE = Path(r"D:/Dados_TSE/data/analise")
FONTES = [
    ("Presidente 2T", "presidente", "ranking_zonas_presidente_2022_2t.csv"),
    ("Deputado Federal 1T", "depfederal", "ranking_zonas_depfederal_2022_1t.csv"),
]


def ler(nome):
    pts = []
    for r in csv.DictReader((ANALISE / nome).open(encoding="utf-8-sig"), delimiter=";"):
        if not r["centro_lat"]:
            continue
        pts.append({
            "z": int(r["nr_zona"]), "sede": r["municipio_sede"], "nm": r["municipios"],
            "lat": float(r["centro_lat"]), "lon": float(r["centro_lon"]),
            "dir": int(r["vot_dir"]), "esq": int(r["vot_esq"]), "cen": int(r["vot_cen"]),
            "val": int(r["validos"]),
            "pdir": float(r["pct_dir"]), "pesq": float(r["pct_esq"]), "pcen": float(r["pct_cen"]),
            "venc": r["vencedor"], "loc": r["qt_locais"],
        })
    return pts


PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapa de Calor — Zonas Eleitorais SP</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<style>
  html,body{height:100%;margin:0}
  body{font-family:system-ui,Segoe UI,Arial,sans-serif;display:flex;flex-direction:column}
  #map{flex:1;min-height:0}
  .bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid #ddd;background:#fff;z-index:1000}
  .faixa{display:flex;align-items:center;gap:5px;font-size:12px;color:#333}
  .faixa input[type=range]{width:104px}
  .exp{background:#0a7d34;color:#fff;border-color:#0a7d34;font-weight:600}
  .bar b{font-size:14px;margin-right:4px}
  button{padding:6px 11px;border:1px solid #999;border-radius:8px;background:#eee;cursor:pointer;font-size:13px}
  button.on{background:#2d6cdf;color:#fff;border-color:#2d6cdf;font-weight:600}
  a{color:#2d6cdf;text-decoration:none;font-size:13px}
  .legend{background:#fff;padding:8px 10px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.3);font-size:12px;line-height:1.6}
  .legend i{display:inline-block;width:12px;height:12px;margin-right:6px;border-radius:50%}
  .ajuda{position:absolute;top:60px;left:10px;z-index:1000;max-width:262px;background:#fff;
    border:1px solid #cfd8e3;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.18);font-size:12.5px}
  .ajuda-h{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 10px;border-bottom:1px solid #eef2f6}
  .ajuda-h b{font-size:13px}
  .ajuda-h button{padding:0 9px;border:1px solid #bbb;border-radius:6px;background:#f2f2f2;cursor:pointer;font-weight:700}
  .ajuda-b{padding:9px 11px;color:#333;line-height:1.5}.ajuda-b p{margin:0 0 7px}
  .ajuda.min .ajuda-b{display:none}
</style>
</head>
<body>
<div class="bar">
  <b>Cargo:</b>
  <button data-cargo="depfederal" class="on" onclick="selc('depfederal')">Dep. Federal 1T</button>
  <button data-cargo="presidente" onclick="selc('presidente')">Presidente 2T</button>
  <b style="margin-left:10px">Mostrar:</b>
  <button data-modo="ambos" class="on" onclick="selmodo('ambos')">Ambos</button>
  <button data-modo="dir" onclick="selmodo('dir')">Só Direita</button>
  <button data-modo="esq" onclick="selmodo('esq')">Só Esquerda</button>
  <b style="margin-left:10px">Total de votos:</b>
  <span class="faixa"><input type="range" id="rmin" oninput="onrange()"> a
    <input type="range" id="rmax" oninput="onrange()"> <span id="rlbl"></span></span>
  <button class="exp" onclick="exportar()">⬇️ Excel (filtrados)</button>
  <span id="cont" style="color:#555;font-size:12px;margin-left:6px"></span>
  <span style="margin-left:auto"><a href="../mapas.html">← Mapas</a></span>
</div>
<div id="map"></div>
<div id="ajuda" class="ajuda">
  <div class="ajuda-h"><b>Como ler este mapa</b>
    <button onclick="var a=document.getElementById('ajuda');a.classList.toggle('min');this.textContent=a.classList.contains('min')?'+':'–'">–</button></div>
  <div class="ajuda-b">
    <p><b>Cor</b> = quem teve mais votos: <b style="color:#08519c">azul = direita</b>, <b style="color:#a50f15">vermelho = esquerda</b>. Tom mais escuro = venceu por maior margem.</p>
    <p><b>Tamanho</b> do círculo = total de votos válidos.</p>
    <p><b>Cargo</b>: alterna Dep. Federal / Presidente. <b>Mostrar</b>: Ambos ou isola um lado.</p>
    <p><b>Total de votos</b>: arraste os controles para mostrar só zonas cujo total de votos
       (tamanho) está na faixa mín–máx. Subir o mínimo mantém só as zonas maiores.</p>
    <p><b>⬇️ Excel</b>: baixa a planilha só com as zonas que estão no filtro atual.</p>
    <p>Clique num círculo para ver os números da zona.</p>
  </div>
</div>
<script>
const DADOS = __DADOS__;
let cargo='depfederal', modo='ambos', layer=null, rmin=0, rmax=1e12;
const map = L.map('map').setView([-22.4,-48.5], 7);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {attribution:'Tiles &copy; Esri', maxZoom:16}).addTo(map);

function fmt(n){ return n.toLocaleString('pt-BR'); }
function raio(v){ return Math.max(4, Math.sqrt(v)/22); }
// cor por VENCEDOR; mais escuro = venceu por maior margem (margem em pontos %)
function shade(win, marg){
  const t = Math.max(.18, Math.min(1, marg/40));           // 0..40 pts -> 0..1
  if(win==='dir'){ // claro #cfe0f2 -> escuro #08306b
    return `rgb(${Math.round(207-199*t)},${Math.round(224-176*t)},${Math.round(242-135*t)})`;
  } // esq: claro #fcd3c4 -> escuro #67000d
  return `rgb(${Math.round(252-149*t)},${Math.round(211-211*t)},${Math.round(196-183*t)})`;
}

function passa(d){
  const dirWin = d.dir >= d.esq;
  if(modo==='dir' && !dirWin) return false;
  if(modo==='esq' &&  dirWin) return false;
  if(d.val < rmin || d.val > rmax) return false;
  return true;
}
function draw(){
  if(layer) map.removeLayer(layer);
  layer=L.layerGroup();
  let n=0;
  DADOS[cargo].filter(passa).forEach(d=>{
    const dirWin = d.dir >= d.esq;
    n++;
    const win = dirWin?'dir':'esq';
    const marg = Math.abs(d.pdir - d.pesq);
    L.circleMarker([d.lat,d.lon],{radius:raio(d.val),fillColor:shade(win,marg),color:'#2b2b2b',
       weight:.5,opacity:.55,fillOpacity:.85})
     .bindPopup(`<b>Zona ${d.z}</b> — ${d.sede}<br>Municípios: ${d.nm}<br>`+
       `<b style="color:${dirWin?'#08519c':'#a50f15'}">Venceu: ${dirWin?'DIREITA':'ESQUERDA'}</b> `+
       `(margem ${marg.toFixed(1)} pts)<br>`+
       `Direita: ${d.pdir.toFixed(1)}% (${fmt(d.dir)})<br>`+
       `Esquerda: ${d.pesq.toFixed(1)}% (${fmt(d.esq)})<br>`+
       `Centro: ${d.pcen.toFixed(1)}% (${fmt(d.cen)}) · válidos ${fmt(d.val)}`)
     .addTo(layer);
  });
  layer.addTo(map);
  const el=document.getElementById('cont'); if(el) el.textContent = n+' zonas';
}
function selc(c){cargo=c;document.querySelectorAll('[data-cargo]').forEach(b=>b.classList.toggle('on',b.dataset.cargo===c));draw();}
function selmodo(m){modo=m;document.querySelectorAll('[data-modo]').forEach(b=>b.classList.toggle('on',b.dataset.modo===m));draw();}
function onrange(){ let a=+document.getElementById('rmin').value, b=+document.getElementById('rmax').value;
  if(a>b){const t=a;a=b;b=t;} rmin=a; rmax=b;
  document.getElementById('rlbl').textContent=fmt(rmin)+'–'+fmt(rmax); draw(); }
function exportar(){
  const rows=DADOS[cargo].filter(passa).map(d=>({
    nr_zona:d.z, municipio_sede:d.sede, municipios:d.nm, qt_locais:d.loc,
    vot_dir:d.dir, vot_esq:d.esq, vot_cen:d.cen, validos:d.val,
    pct_dir:d.pdir, pct_esq:d.pesq, pct_cen:d.pcen,
    vencedor:(d.dir>=d.esq?'DIREITA':'ESQUERDA'), centro_lat:d.lat, centro_lon:d.lon
  })).sort((a,b)=>b.vot_dir-a.vot_dir);
  if(!rows.length){ alert('Nenhuma zona no filtro atual.'); return; }
  const ws=XLSX.utils.json_to_sheet(rows), wb=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, (cargo==='depfederal'?'Dep Federal':'Presidente'));
  XLSX.writeFile(wb, 'zonas_'+cargo+'_'+modo+'.xlsx');
}
(function(){ let mn=Infinity,mx=0;
  Object.values(DADOS).forEach(a=>a.forEach(d=>{ if(d.val<mn)mn=d.val; if(d.val>mx)mx=d.val; }));
  rmin=mn; rmax=mx; const a=document.getElementById('rmin'), b=document.getElementById('rmax');
  a.min=b.min=mn; a.max=b.max=mx; a.value=mn; b.value=mx; a.step=b.step=Math.max(1,Math.round((mx-mn)/200));
  document.getElementById('rlbl').textContent=fmt(rmin)+'–'+fmt(rmax);
})();

const lg=L.control({position:'bottomright'});
lg.onAdd=function(){const d=L.DomUtil.create('div','legend');
  d.innerHTML='<b>Quem teve mais votos</b><br>'+
    '<i style="background:#08306b"></i> Direita venceu (azul)<br>'+
    '<i style="background:#67000d"></i> Esquerda venceu (vermelho)<br>'+
    '<span style="color:#666">tom mais escuro = venceu por maior margem<br>tamanho do círculo = votos válidos</span>';
  return d;};
lg.addTo(map);
draw();
</script>
</body>
</html>"""


def main():
    dados = {slug: ler(nome) for _, slug, nome in FONTES}
    for rot, slug, _ in FONTES:
        print(f"{rot}: {len(dados[slug])} zonas com centroide")
    out = ANALISE / "mapa_calor_zonas.html"
    out.write_text(PAGE.replace("__DADOS__", json.dumps(dados, ensure_ascii=False)), encoding="utf-8")
    print(f"OK: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
