#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_mapa_escolas_zonas.py
FUNCAO    : Mapa (Leaflet) de PINOS por escola/local de votacao (cluster p/ 10.845
            pontos) + CIRCULO da ZONA. Cor por VENCEDOR (quem teve mais votos):
            azul=direita, vermelho=esquerda; tom mais escuro = maior margem.
            Filtro Ambos/So Direita/So Esquerda; alterna cargo (Dep.Fed/Presid);
            filtro por tipo de local. Tamanho do pino ~ votos do local.
FONTES    : data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv (pinos/endereco/tipo)
            data/analise/ranking_zonas_{depfederal,presidente}_{ano}_{t}t.csv (zonas)
            data/db/sao_paulo.duckdb (votos por local)
SAIDA     : data/analise/mapa_escolas_zonas.html
USO       : python _scripts/gerar_mapa_escolas_zonas.py
"""
import csv
import json
import sys
from pathlib import Path

import duckdb

ANALISE = Path(r"D:/Dados_TSE/data/analise")
DB = "D:/Dados_TSE/data/db/sao_paulo.duckdb"


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ler_votos_local(ano):
    con = duckdb.connect(DB, read_only=True)
    m = {}
    for mun, z, loc, dd, de, pd, pe in con.execute(f"""
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='DIREITA'),0),
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='ESQUERDA'),0),
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='DIREITA'),0),
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='ESQUERDA'),0)
        FROM fact_votacao_secao v
        LEFT JOIN vw_candidato_campo c ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
       WHERE v.ano_eletivo={ano} GROUP BY 1,2,3
    """).fetchall():
        m[(mun, int(z), int(loc))] = (dd, de, pd, pe)
    con.close()
    return m


def ler_pinos(ano, votos):
    p = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    if not p.exists():
        p = ANALISE / f"enderecos_locais_zona_sp_{ano}.csv"
    pins = []
    for r in csv.DictReader(p.open(encoding="utf-8-sig"), delimiter=";"):
        la, lo = num(r.get("lat")), num(r.get("lon"))
        if la is None or lo is None:
            continue
        logr = (r.get("logradouro") or "").strip()
        n_ = (r.get("numero") or "").strip()
        end = (f"{logr}, {n_}".strip(", ") if logr else (r.get("ds_endereco") or "")).strip()
        key = (r["cd_municipio_tse"], int(r["nr_zona"]), int(r["nr_local_votacao"]))
        dd, de, pd, pe = votos.get(key, (0, 0, 0, 0))
        pins.append([round(la, 6), round(lo, 6), r.get("nm_local_votacao", ""),
                     end, r.get("nm_bairro", ""), int(r["nr_zona"]),
                     r.get("tipo_local", "Outros") or "Outros",
                     int(dd), int(de), int(pd), int(pe)])
    return pins


def ler_zonas(ano):
    def rd(nome):
        p = ANALISE / nome
        d = {}
        if p.exists():
            for r in csv.DictReader(p.open(encoding="utf-8-sig"), delimiter=";"):
                d[int(r["nr_zona"])] = r
        return d
    dep = rd(f"ranking_zonas_depfederal_{ano}_1t.csv")
    pres = rd(f"ranking_zonas_presidente_{ano}_2t.csv")
    zonas = {}
    for z, r in dep.items():
        if not r.get("centro_lat"):
            continue
        pr = pres.get(z, {})
        zonas[z] = {
            "sede": r.get("municipio_sede", ""), "clat": num(r["centro_lat"]), "clon": num(r["centro_lon"]),
            "loc": r.get("qt_locais", ""),
            "dep_vdir": int(r.get("vot_dir") or 0), "dep_vesq": int(r.get("vot_esq") or 0),
            "pres_vdir": int(pr.get("vot_dir") or 0), "pres_vesq": int(pr.get("vot_esq") or 0),
        }
    return zonas


PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapa — Escolas / locais de votação SP (quem venceu)</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js"></script>
<style>
  html,body{height:100%;margin:0}
  body{font-family:system-ui,Segoe UI,Arial,sans-serif;display:flex;flex-direction:column}
  #map{flex:1;min-height:0}
  .bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid #ddd;background:#fff;z-index:1000}
  .bar b{font-size:13px}
  button{padding:6px 11px;border:1px solid #999;border-radius:8px;background:#eee;cursor:pointer;font-size:13px}
  button.on{background:#2d6cdf;color:#fff;border-color:#2d6cdf;font-weight:600}
  a{color:#2d6cdf;text-decoration:none;font-size:13px;margin-left:auto}
  .legend{background:#fff;padding:7px 10px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.3);font-size:12px}
  .legend i{display:inline-block;width:11px;height:11px;margin-right:5px;border-radius:50%}
  body.grafo .marker-cluster{display:none!important}  /* no modo grafo, esconde as bolhas do cluster */
</style>
</head>
<body>
<div class="bar">
  <b>Cargo:</b>
  <button data-cargo="dep" class="on" onclick="selc('dep')">Dep. Federal</button>
  <button data-cargo="pres" onclick="selc('pres')">Presidente</button>
  <b style="margin-left:8px">Mostrar:</b>
  <button data-modo="ambos" class="on" onclick="selmodo('ambos')">Ambos</button>
  <button data-modo="dir" onclick="selmodo('dir')">Só Direita</button>
  <button data-modo="esq" onclick="selmodo('esq')">Só Esquerda</button>
  <b style="margin-left:8px">Camadas:</b>
  <button id="bEsc" class="on" onclick="toggle('esc')">Escolas</button>
  <button id="bZon" onclick="toggle('zon')">Zonas</button>
  <b style="margin-left:8px">Extra:</b>
  <button id="bGrafo" title="Abre todos os clusters visíveis de uma vez — ligações do centro até cada escola (aproxime o zoom)" onclick="toggleGrafo()">🕸️ Modo grafo</button>
  <b style="margin-left:8px">Tipo:</b>
  <span id="tipoBar" style="display:flex;gap:6px;flex-wrap:wrap"></span>
  <span id="cont" style="color:#555;font-size:12px"></span>
  <a href="../mapas.html">← Mapas</a>
</div>
<div id="map"></div>
<script>
const PINS = __PINS__, ZONAS = __ZONAS__, TIPOS = __TIPOS__;
let cargo='dep', modo='ambos', tipoOn=new Set(TIPOS);
const map=L.map('map').setView([-22.9,-47.1],9);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {attribution:'Tiles &copy; Esri',maxZoom:16}).addTo(map);
function fmt(n){ return (n||0).toLocaleString('pt-BR'); }
// cor por vencedor; tom mais escuro = maior margem (0..40 pts de 2 vias)
function shade(win, marg){
  const t=Math.max(.18,Math.min(1,marg/40));
  if(win==='dir') return `rgb(${Math.round(207-199*t)},${Math.round(224-176*t)},${Math.round(242-135*t)})`;
  return `rgb(${Math.round(252-149*t)},${Math.round(211-211*t)},${Math.round(196-183*t)})`;
}
function vlocal(p){ return cargo==='dep'?[p[7],p[8]]:[p[9],p[10]]; }   // [dir, esq]
function margpts(dir,esq){ const t=dir+esq; return t? 100*Math.abs(dir-esq)/t : 0; }

// ESCOLAS (cluster)
let cluster=L.markerClusterGroup({maxClusterRadius:48,disableClusteringAtZoom:14});
function raioLocal(t){ return Math.max(3.5, Math.min(13, Math.sqrt(t)/4.5)); }
function drawPins(){
  cluster.clearLayers(); let n=0;
  PINS.forEach(p=>{
    if(!tipoOn.has(p[6])) return;
    const [dir,esq]=vlocal(p); if(dir+esq===0) return;
    const dirWin=dir>=esq;
    if(modo==='dir'&&!dirWin) return; if(modo==='esq'&&dirWin) return;
    n++;
    const m=L.circleMarker([p[0],p[1]],{radius:raioLocal(dir+esq),
       fillColor:shade(dirWin?'dir':'esq',margpts(dir,esq)),color:'#2b2b2b',weight:.5,fillOpacity:.9});
    m.bindPopup(`<b>${p[2]}</b><br><i>${p[6]}</i><br>${p[3]}${p[4]?' - '+p[4]:''}<br>Zona ${p[5]}<br>`+
      `<b style="color:${dirWin?'#08519c':'#a50f15'}">Venceu: ${dirWin?'DIREITA':'ESQUERDA'}</b><br>`+
      `Dep.Federal — Dir ${fmt(p[7])} · Esq ${fmt(p[8])}<br>`+
      `Presidente — Dir ${fmt(p[9])} · Esq ${fmt(p[10])}`);
    cluster.addLayer(m);
  });
  const el=document.getElementById('cont'); if(el) el.textContent=n.toLocaleString('pt-BR')+' locais';
}
// ZONAS (circulo)
let zonLayer=L.layerGroup();
function drawZonas(){
  zonLayer.clearLayers();
  Object.keys(ZONAS).forEach(z=>{
    const o=ZONAS[z]; if(o.clat==null) return;
    const dir=cargo==='dep'?o.dep_vdir:o.pres_vdir, esq=cargo==='dep'?o.dep_vesq:o.pres_vesq;
    const dirWin=dir>=esq;
    if(modo==='dir'&&!dirWin) return; if(modo==='esq'&&dirWin) return;
    const v=dir+esq;
    L.circleMarker([o.clat,o.clon],{radius:Math.max(6,Math.sqrt(v)/20),
       fillColor:shade(dirWin?'dir':'esq',margpts(dir,esq)),color:'#222',weight:.7,opacity:.6,fillOpacity:.4})
     .bindPopup(`<b>Zona ${z}</b> — ${o.sede}<br>Locais: ${o.loc}<br>`+
       `<b style="color:${dirWin?'#08519c':'#a50f15'}">Venceu: ${dirWin?'DIREITA':'ESQUERDA'}</b><br>`+
       `Dir ${fmt(dir)} · Esq ${fmt(esq)}`)
     .addTo(zonLayer);
  });
}
function redraw(){ drawPins(); drawZonas(); if(grafoOn) setTimeout(drawGrafo,60); }
// MODO GRAFO: abre todos os clusters visíveis de uma vez (hub-and-spoke, estilo grafo)
let grafoOn=false; const graphLayer=L.layerGroup();
const grafoRefresh=()=>setTimeout(drawGrafo,60);
function drawGrafo(){
  graphLayer.clearLayers();
  const el=document.getElementById('cont');
  if(!grafoOn) return;
  const z=map.getZoom();
  if(z<11){ if(el) el.textContent='🕸️ Modo grafo: aproxime o zoom para ver as ligações'; return; }
  if(z>=14){ if(el) el.textContent='🕸️ Modo grafo: afaste um pouco (neste zoom os pontos já estão separados)'; return; }
  const b=map.getBounds().pad(0.12); let n=0;
  cluster._featureGroup.getLayers().forEach(l=>{
    if(l instanceof L.MarkerCluster){
      const c=l.getLatLng(); if(!b.contains(c)) return;
      l.getAllChildMarkers().forEach(m=>{
        const ll=m.getLatLng();
        graphLayer.addLayer(L.polyline([c,ll],{color:'#334155',weight:.9,opacity:.6,interactive:false}));
        graphLayer.addLayer(L.circleMarker(ll,{radius:3,fillColor:m.options.fillColor,
          color:'#111',weight:.5,fillOpacity:1,interactive:false}));
        n++;
      });
    }
  });
  if(el) el.textContent='🕸️ '+n.toLocaleString('pt-BR')+' ligações';
}
function toggleGrafo(){
  grafoOn=!grafoOn;
  document.getElementById('bGrafo').classList.toggle('on',grafoOn);
  document.body.classList.toggle('grafo',grafoOn);   // esconde as bolhas do cluster p/ ver a teia
  if(grafoOn){ graphLayer.addTo(map); map.on('moveend',grafoRefresh); }
  else{ map.off('moveend',grafoRefresh); map.removeLayer(graphLayer); }
  drawGrafo();
}
function selc(c){ cargo=c; document.querySelectorAll('[data-cargo]').forEach(b=>b.classList.toggle('on',b.dataset.cargo===c)); redraw(); }
function selmodo(m){ modo=m; document.querySelectorAll('[data-modo]').forEach(b=>b.classList.toggle('on',b.dataset.modo===m)); redraw(); }
function toggle(k){
  if(k==='esc'){ const on=map.hasLayer(cluster); on?map.removeLayer(cluster):map.addLayer(cluster); document.getElementById('bEsc').classList.toggle('on',!on); }
  else{ const on=map.hasLayer(zonLayer); on?map.removeLayer(zonLayer):map.addLayer(zonLayer); document.getElementById('bZon').classList.toggle('on',!on); }
}
// filtro por tipo
(function(){ const bar=document.getElementById('tipoBar');
  TIPOS.forEach(t=>{ const b=document.createElement('button'); b.textContent=t; b.className='on';
    b.onclick=()=>{ if(tipoOn.has(t)){tipoOn.delete(t);b.classList.remove('on');}else{tipoOn.add(t);b.classList.add('on');} drawPins(); };
    bar.appendChild(b); }); })();
redraw(); cluster.addTo(map);
const lg=L.control({position:'bottomright'});
lg.onAdd=function(){const d=L.DomUtil.create('div','legend');
  d.innerHTML='<b>Quem teve mais votos no local</b><br>'+
    '<i style="background:#08306b"></i> Direita venceu<br>'+
    '<i style="background:#67000d"></i> Esquerda venceu<br>'+
    '<span style="color:#666">tom mais escuro = maior margem<br>tamanho = votos do local</span>';return d;};
lg.addTo(map);
</script>
</body>
</html>"""


def main():
    ano = 2022
    votos = ler_votos_local(ano)
    pins = ler_pinos(ano, votos)
    zonas = ler_zonas(ano)
    from collections import Counter
    freq = Counter(p[6] for p in pins)
    tipos = [t for t, _ in freq.most_common()]
    print(f"pinos: {len(pins):,} | zonas: {len(zonas)} | tipos: {dict(freq)}")
    out = ANALISE / "mapa_escolas_zonas.html"
    html = PAGE.replace("__PINS__", json.dumps(pins, ensure_ascii=False))
    html = html.replace("__ZONAS__", json.dumps({str(k): v for k, v in zonas.items()}, ensure_ascii=False))
    html = html.replace("__TIPOS__", json.dumps(tipos, ensure_ascii=False))
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out}  ({out.stat().st_size/1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
