#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_mapa_local_nacional.py
FUNCAO    : Mapa (Leaflet) interativo NACIONAL por LOCAL de votacao (2022),
            com dados de TODOS os 27 estados embutidos (cluster).
            Pinos = locais de votacao; cor por VENCEDOR do bloco
            Direita/Esquerda; tom mais escuro = maior margem; tamanho = votos.
            Cargos: PRESIDENTE (2T), DEP. FEDERAL (1T) e GOVERNADOR
            (turno decisivo por UF). Filtro por UF, cargo, Ambos/SóDir/SóEsq,
            tipo de local, busca por municipio e MODO GRAFO.
FONTES    : data/db/brasil.duckdb (fact_votacao_secao + dim_local_votacao
            + vw_candidato_campo + dim_municipio)
SAIDA     : data/analise/mapa_local_nacional_2022.html
USO       : python _scripts/gerar_mapa_local_nacional.py
Criado    : 2026-09-28
=============================================================================
"""
import json
import sys
from pathlib import Path

import duckdb

ANALISE = Path(__file__).resolve().parent.parent / "data" / "analise"
DB = Path(__file__).resolve().parent.parent / "data" / "db" / "brasil.duckdb"
ANO = 2022

CARGOS = [
    ("presidente", "Presidente (2º turno)", 2, "presidente"),
    ("depfederal", "Dep. Federal (1º turno)", 1, "deputado federal"),
    ("governador", "Governador (2º/1º turno)", None, "governador"),
]


def cargas_votos(con, cargo, turno):
    """Retorna votos por (municipio, zona, local) para um cargo/turno fixos.
    Chave: '{cd_municipio}.{zona}.{local}' -> (dir, esq, cen)"""
    return con.execute(f"""
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
               COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='DIREITA'),0)  AS d,
               COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='ESQUERDA'),0) AS e,
               COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='CENTRO'),0)   AS cn
        FROM fact_votacao_secao v
        LEFT JOIN vw_candidato_campo c
               ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
        WHERE v.ano_eletivo={ANO} AND UPPER(v.ds_cargo)=UPPER('{cargo}')
          AND v.nr_turno={turno}
        GROUP BY 1,2,3
    """).fetchall()


def turno_decisivo_governador(con):
    """UF -> turno a usar (2 se existe 2T, senao 1)."""
    return {r[0]: r[1] for r in con.execute(f"""
        SELECT m.sg_uf, MAX(v.nr_turno)
        FROM fact_votacao_secao v
        JOIN dim_municipio m ON m.cd_municipio_tse=v.cd_municipio_tse
        WHERE v.ano_eletivo={ANO} AND UPPER(v.ds_cargo)='GOVERNADOR'
        GROUP BY 1
    """).fetchall()}


PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapa Brasil — Locais de votação 2022 (quem venceu)</title>
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
  select{padding:5px 8px;border:1px solid #999;border-radius:8px;font-size:13px}
  button{padding:6px 11px;border:1px solid #999;border-radius:8px;background:#eee;cursor:pointer;font-size:13px}
  button.on{background:#2d6cdf;color:#fff;border-color:#2d6cdf;font-weight:600}
  input{padding:6px 8px;border:1px solid #999;border-radius:8px;font-size:13px;min-width:180px}
  a{color:#2d6cdf;text-decoration:none;font-size:13px;margin-left:auto}
  .legend{background:#fff;padding:7px 10px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.3);font-size:12px}
  .legend i{display:inline-block;width:11px;height:11px;margin-right:5px;border-radius:50%}
  body.grafo .marker-cluster{display:none!important}
</style>
</head>
<body>
<div class="bar">
  <b>UF:</b>
  <select id="ufSel" onchange="applyUF()"></select>
  <b>Cargo:</b>
  <select id="cargoSel" onchange="applyCargo()"></select>
  <b>Mostrar:</b>
  <button data-modo="ambos" class="on" onclick="selmodo('ambos')">Ambos</button>
  <button data-modo="dir" onclick="selmodo('dir')">Só Direita</button>
  <button data-modo="esq" onclick="selmodo('esq')">Só Esquerda</button>
  <b style="margin-left:8px">Tipo:</b>
  <span id="tipoBar" style="display:flex;gap:6px;flex-wrap:wrap"></span>
  <input id="busca" placeholder="Município..." oninput="redraw()">
  <b style="margin-left:8px">Extra:</b>
  <button id="bGrafo" title="Abre os clusters visíveis (use zoom) — ligações centro→escola" onclick="toggleGrafo()">🕸️ Modo grafo</button>
  <span id="cont" style="color:#555;font-size:12px"></span>
  <a href="index.html">← Índice</a>
</div>
<div id="map"></div>
<script>
const PINS = __PINS__, UFS = __UFS__, TIPOS = __TIPOS__;
const CARGOS = ['presidente','depfederal','governador'];
const OFF = {presidente:[10,11,12], depfederal:[13,14,15], governador:[16,17,18]};
let cargo='presidente', modo='ambos', tipoOn=new Set(TIPOS), uf='BR';
const map=L.map('map').setView([-14.2,-51.9],4);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {attribution:'Tiles &copy; Esri',maxZoom:16}).addTo(map);
function fmt(n){ return (n||0).toLocaleString('pt-BR'); }
function shade(win, marg){
  const t=Math.max(.18,Math.min(1,marg/40));
  if(win==='dir') return `rgb(${Math.round(207-199*t)},${Math.round(224-176*t)},${Math.round(242-135*t)})`;
  return `rgb(${Math.round(252-149*t)},${Math.round(211-211*t)},${Math.round(196-183*t)})`;
}
function margpts(dir,esq){ const t=dir+esq; return t? 100*Math.abs(dir-esq)/t : 0; }
function pinV(p){ const o=OFF[cargo]; return [p[o[0]],p[o[1]]]; }

let cluster=L.markerClusterGroup({maxClusterRadius:48,disableClusteringAtZoom:15});
function raioLocal(t){ return Math.max(3.5, Math.min(13, Math.sqrt(t)/4.5)); }
function drawPins(){
  cluster.clearLayers(); let n=0;
  const q=(document.getElementById('busca').value||'').toLowerCase().trim();
  PINS.forEach(p=>{
    if(uf!=='BR' && p[2]!==uf) return;
    if(!tipoOn.has(p[8])) return;
    if(q && String(p[3]).toLowerCase().indexOf(q)===-1) return;
    const [dir,esq]=pinV(p); if(dir+esq===0) return;
    const dirWin=dir>=esq;
    if(modo==='dir'&&!dirWin) return; if(modo==='esq'&&dirWin) return;
    n++;
    const m=L.circleMarker([p[0],p[1]],{radius:raioLocal(dir+esq),
       fillColor:shade(dirWin?'dir':'esq',margpts(dir,esq)),color:'#2b2b2b',weight:.5,fillOpacity:.9});
    const pv=OFF.presidente, df=OFF.depfederal, gv=OFF.governador;
    const pdir=p[pv[0]],pesq=p[pv[1]],ddir=p[df[0]],desq=p[df[1]],gdir=p[gv[0]],gesq=p[gv[1]];
    const wD=pdir>=pesq, wD2=ddir>=desq, wG=gdir>=gesq;
    m.bindPopup(`<b>${p[5]}</b><br><i>${p[8]}</i> · Zona ${p[4]}<br>`+
      `${p[6]}${p[7]?' - '+p[7]:''}<br>${p[3]} (${p[2]}) CEP ${p[9]}<hr>`+
      `<b style="color:${dirWin?'#08519c':'#a50f15'}">Venceu: ${dirWin?'DIREITA':'ESQUERDA'}</b><br>`+
      `<span style="color:#777">Presidente — Dir ${fmt(pdir)} · Esq ${fmt(pesq)}${wD?` &#9733;`:''}</span><br>`+
      `<span style="color:#777">Dep.Federal — Dir ${fmt(ddir)} · Esq ${fmt(desq)}${wD2?` &#9733;`:''}</span><br>`+
      `<span style="color:#777">Governador — Dir ${fmt(gdir)} · Esq ${fmt(gesq)}${wG?` &#9733;`:''}</span>`);
    cluster.addLayer(m);
  });
  const el=document.getElementById('cont'); if(el) el.textContent=n.toLocaleString('pt-BR')+' locais';
}
let grafoOn=false; const graphLayer=L.layerGroup();
const grafoRefresh=()=>setTimeout(drawGrafo,60);
function drawGrafo(){
  graphLayer.clearLayers();
  const el=document.getElementById('cont'); if(!grafoOn) return;
  const z=map.getZoom();
  if(z<7){ if(el) el.textContent='🕸️ Modo grafo: aproxime o zoom para ver as ligações'; return; }
  if(z>=15){ if(el) el.textContent='🕸️ Modo grafo: afaste um pouco'; return; }
  const b=map.getBounds().pad(0.12); let n=0;
  cluster._featureGroup.getLayers().forEach(l=>{
    if(!(l instanceof L.MarkerCluster)) return;
    const c=l.getLatLng(); if(!b.contains(c)) return;
    l.getAllChildMarkers().forEach(m=>{
      const ll=m.getLatLng();
      graphLayer.addLayer(L.polyline([c,ll],{color:'#334155',weight:.9,opacity:.6,interactive:false}));
      graphLayer.addLayer(L.circleMarker(ll,{radius:3,fillColor:m.options.fillColor,
        color:'#111',weight:.5,fillOpacity:1,interactive:false}));
      n++;
    });
  });
  if(el) el.textContent='🕸️ '+n.toLocaleString('pt-BR')+' ligações';
}
function toggleGrafo(){
  grafoOn=!grafoOn;
  document.getElementById('bGrafo').classList.toggle('on',grafoOn);
  document.body.classList.toggle('grafo',grafoOn);
  if(grafoOn){ graphLayer.addTo(map); map.on('moveend',grafoRefresh); }
  else{ map.off('moveend',grafoRefresh); map.removeLayer(graphLayer); }
  drawGrafo();
}
function redraw(){ drawPins(); if(grafoOn) setTimeout(drawGrafo,60); }
function selmodo(m){ modo=m; document.querySelectorAll('[data-modo]').forEach(b=>b.classList.toggle('on',b.dataset.modo===m)); redraw(); }
function applyUF(){ uf=document.getElementById('ufSel').value; redraw(); }
function applyCargo(){
  cargo=document.getElementById('cargoSel').value; redraw();
}
(function(){ const s=document.getElementById('ufSel');
  const all=document.createElement('option'); all.value='BR'; all.textContent='🇧🇷 Todo o Brasil'; s.appendChild(all);
  UFS.forEach(u=>{ const o=document.createElement('option'); o.value=u.o; o.textContent=u.n; s.appendChild(o); });
  const c=document.getElementById('cargoSel');
  [['presidente','Presidente (2º turno)'],['depfederal','Dep. Federal (1º turno)'],['governador','Governador (turno decisivo)']]
   .forEach(x=>{ const o=document.createElement('option'); o.value=x[0]; o.textContent=x[1]; c.appendChild(o); });
})();
(function(){ const bar=document.getElementById('tipoBar');
  TIPOS.forEach(t=>{ const b=document.createElement('button'); b.textContent=t; b.className='on';
    b.onclick=()=>{ if(tipoOn.has(t)){tipoOn.delete(t);b.classList.remove('on');}else{tipoOn.add(t);b.classList.add('on');} drawPins(); };
    bar.appendChild(b); }); })();
redraw(); cluster.addTo(map);
const lg=L.control({position:'bottomright'});
lg.onAdd=function(){const d=L.DomUtil.create('div','legend');
  d.innerHTML='<b>Vencedor do bloco no local</b><br>'+
    '<i style="background:#08306b"></i> Direita venceu<br>'+
    '<i style="background:#67000d"></i> Esquerda venceu<br>'+
    '<span style="color:#666">tom mais escuro = maior margem<br>tamanho = votos do local</span>';return d;};
lg.addTo(map);
</script>
</body>
</html>"""


def main():
    con = duckdb.connect(str(DB), read_only=True)

    gov_turno = turno_decisivo_governador(con)

    votos = {}
    for slug, label, turno, cargov in CARGOS:
        if slug == "governador":
            for uf, t in gov_turno.items():
                rows = con.execute(f"""
                    SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
                      COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='DIREITA'),0),
                      COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='ESQUERDA'),0),
                      COALESCE(SUM(v.qt_votos) FILTER (WHERE c.campo='CENTRO'),0)
                    FROM fact_votacao_secao v
                    LEFT JOIN vw_candidato_campo c
                           ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
                    JOIN dim_municipio m ON m.cd_municipio_tse=v.cd_municipio_tse
                    WHERE v.ano_eletivo={ANO} AND UPPER(v.ds_cargo)='GOVERNADOR'
                      AND v.nr_turno={t} AND m.sg_uf='{uf}'
                    GROUP BY 1,2,3""").fetchall()
                for r in rows:
                    votos[(slug, f"{r[0]}.{r[1]}.{r[2]}")] = (r[3], r[4], r[5])
        else:
            rows = cargas_votos(con, cargov, turno)
            for r in rows:
                votos[(slug, f"{r[0]}.{r[1]}.{r[2]}")] = (r[3], r[4], r[5])
        print(f"  {slug}: {len([k for k in votos if k[0]==slug]):,} locais com votos")

    # base de locais: dim_local_votacao 2022 (endereço/lat/lon)
    locais = con.execute(f"""
        SELECT d.cd_municipio_tse, d.nr_zona, d.nr_local_votacao,
               d.nm_local_votacao, d.ds_tipo_local, d.ds_endereco,
               d.nm_bairro, d.nr_cep, d.nr_latitude, d.nr_longitude,
               m.nm_municipio_tse, m.sg_uf
        FROM dim_local_votacao d JOIN dim_municipio m
             ON m.cd_municipio_tse = d.cd_municipio_tse
        WHERE d.ano_eletivo={ANO} AND d.nr_latitude IS NOT NULL
          AND d.nr_latitude != 0 AND d.nr_longitude IS NOT NULL
        ORDER BY d.cd_municipio_tse, d.nr_zona, d.nr_local_votacao""").fetchall()
    con.close()
    print(f"locais com coordenada: {len(locais):,}")

    pins = []
    n_com_voto = 0
    tipos = {}
    for cd, zona, local, nome, tipo, end, bairro, cep, lat, lon, mun, uf in locais:
        key = f"{cd}.{zona}.{local}"
        def g(slug):
            return votos.get((slug, key), (0, 0, 0))
        pd, pe, pc = g("presidente")
        dd, de, dc = g("depfederal")
        gd, ge, gc = g("governador")
        if pd + pe + dd + de + gd + ge > 0:
            n_com_voto += 1
        tipos[tipo or "Outros"] = tipos.get(tipo or "Outros", 0) + 1
        pins.append([round(lat, 6), round(lon, 6), uf, mun, int(zona),
                     nome or "", end or "", bairro or "", tipo or "Outros",
                     cep or "", pd, pe, pc, dd, de, dc, gd, ge, gc])

    ufs = [{"o": u, "n": u} for u in
           sorted({p[2] for p in pins})]
    tipolist = [t for t, _ in sorted(tipos.items(), key=lambda x: -x[1])]
    print(f"pins: {len(pins):,} | com voto: {n_com_voto:,} | tipos: {tipolist}")

    # compacta: remove centavos (votos são ints anyway) e reduz precisão já feita
    out = ANALISE / "mapa_local_nacional_2022.html"
    html = (PAGE.replace("__PINS__", json.dumps(pins, ensure_ascii=False))
                .replace("__UFS__", json.dumps(ufs, ensure_ascii=False))
                .replace("__TIPOS__", json.dumps(tipolist, ensure_ascii=False)))
    out.write_text(html, encoding="utf-8")
    print(f"OK: {out}  ({out.stat().st_size/1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())