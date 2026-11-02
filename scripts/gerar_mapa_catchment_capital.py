#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_mapa_catchment_capital.py
FUNCAO    : Mapa CHEIO (sem vazios) da CAPITAL por CATCHMENT: cada setor censitario
            e atribuido a ESCOLA/urna mais proxima (vizinho mais proximo por
            coordenada) e pintado com o resultado dela. Representa a ABRANGENCIA
            ESTIMADA (nao so o local). Controle Realcar (Neutro/Direita/Esquerda)
            e cargo (Dep.Federal/Presidente).
FONTES    : data/db/sao_paulo.duckdb (votos por local)
            data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv (lat/lon das escolas)
            D:/dados_cnefe/SP_setores_CD2022.gpkg (setores da capital, CD_MUN=3550308)
SAIDA     : data/analise/mapa_catchment_capital.html
USO       : python _scripts/gerar_mapa_catchment_capital.py [ano]
NOTA      : catchment = estimativa (o TSE nao publica onde o eleitor mora).
"""
import csv
import json
import sys
from pathlib import Path

import duckdb

ANALISE = Path(r"D:/Dados_TSE/data/analise")
DB = "D:/Dados_TSE/data/db/sao_paulo.duckdb"
GPKG = "D:/dados_cnefe/SP_setores_CD2022.gpkg"
CAP_TSE = "71072"      # Sao Paulo capital (codigo TSE)
CAP_IBGE = "3550308"   # Sao Paulo capital (codigo IBGE)
TOL = 0.00015


def main():
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    con = duckdb.connect(DB, read_only=True)
    con.execute("INSTALL spatial; LOAD spatial;")

    # votos por local (capital), dep 1T + pres 2T
    vloc = {}
    for r in con.execute(f"""
        SELECT v.nr_zona, v.nr_local_votacao,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='DIREITA'),0) dd,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='ESQUERDA'),0) de,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND v.nr_votavel NOT IN (95,96,97)),0) dv,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='DIREITA'),0) pd,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='ESQUERDA'),0) pe,
          COALESCE(SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND v.nr_votavel NOT IN (95,96,97)),0) pv
        FROM fact_votacao_secao v
        LEFT JOIN vw_candidato_campo c ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
       WHERE v.ano_eletivo={ano} AND v.cd_municipio_tse='{CAP_TSE}'
       GROUP BY 1,2
    """).fetchall():
        vloc[(r[0], r[1])] = r[2:]

    # escolas da capital com lat/lon (do arquivo enriquecido) + votos
    esc = []
    src = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    for r in csv.DictReader(src.open(encoding="utf-8-sig"), delimiter=";"):
        if r["cd_municipio_tse"] != CAP_TSE:
            continue
        try:
            la, lo = float(r["lat"]), float(r["lon"])
        except (ValueError, TypeError):
            continue
        v = vloc.get((int(r["nr_zona"]), int(r["nr_local_votacao"])))
        if not v:
            continue
        esc.append((int(r["nr_local_votacao"]), la, lo, *v))
    print(f"escolas capital c/ voto e geo: {len(esc):,}")

    con.execute("CREATE TEMP TABLE esc(nl INT, lat DOUBLE, lon DOUBLE, dd INT, de INT, dv INT, pd INT, pe INT, pv INT)")
    con.executemany("INSERT INTO esc VALUES (?,?,?,?,?,?,?,?,?)", esc)

    # setores da capital: geometria simplificada + centroide
    con.execute(f"""
        CREATE TEMP TABLE setor AS
        SELECT CAST(CD_SETOR AS VARCHAR) cod, NM_BAIRRO bairro,
               ST_Simplify(geom,{TOL}) g,
               ST_X(ST_Centroid(geom)) cx, ST_Y(ST_Centroid(geom)) cy
          FROM ST_Read('{GPKG}')
         WHERE CAST(CD_MUN AS VARCHAR)='{CAP_IBGE}'
    """)
    ns = con.execute("SELECT count(*) FROM setor").fetchone()[0]

    # atribui cada setor a escola mais proxima (prefiltro por bbox ~5km)
    rows = con.execute("""
        WITH cand AS (
          SELECT s.cod, s.bairro, ST_AsGeoJSON(s.g) gj,
                 e.dd,e.de,e.dv,e.pd,e.pe,e.pv,
                 (s.cx-e.lon)*(s.cx-e.lon)+(s.cy-e.lat)*(s.cy-e.lat) d2
            FROM setor s JOIN esc e
              ON e.lat BETWEEN s.cy-0.06 AND s.cy+0.06
             AND e.lon BETWEEN s.cx-0.06 AND s.cx+0.06
        )
        SELECT cod,bairro,gj,dd,de,dv,pd,pe,pv
          FROM cand
        QUALIFY row_number() OVER (PARTITION BY cod ORDER BY d2)=1
    """).fetchall()
    print(f"setores capital: {ns:,} | atribuidos a uma escola: {len(rows):,}")

    def pct(p, t): return round(100.0*p/t, 1) if t else None
    feats = []
    for cod, bairro, gj, dd, de, dv, pd, pe, pv in rows:
        try:
            geom = json.loads(gj)
        except Exception:
            continue
        feats.append({"type": "Feature", "geometry": geom, "properties": {
            "s": cod, "b": bairro or "",
            "dep_pdir": pct(dd, dv), "dep_pesq": pct(de, dv),
            "pres_pdir": pct(pd, pv), "pres_pesq": pct(pe, pv)}})
    fc = {"type": "FeatureCollection", "features": feats}
    out = ANALISE / "mapa_catchment_capital.html"
    out.write_text(PAGE.replace("__FC__", json.dumps(fc, ensure_ascii=False)), encoding="utf-8")
    print(f"OK: {out}  ({out.stat().st_size/1048576:.1f} MB, {len(feats):,} setores)")
    return 0


PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Catchment por Setor — Capital SP</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
  html,body{height:100%;margin:0}
  body{font-family:system-ui,Segoe UI,Arial,sans-serif;display:flex;flex-direction:column}
  #map{flex:1;min-height:0}
  .bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 14px;border-bottom:1px solid #ddd;background:#fff}
  button{padding:6px 11px;border:1px solid #999;border-radius:8px;background:#eee;cursor:pointer;font-size:13px}
  button.on{background:#2d6cdf;color:#fff;border-color:#2d6cdf;font-weight:600}
  a{color:#2d6cdf;text-decoration:none;font-size:13px;margin-left:auto}
  .legend{background:#fff;padding:7px 10px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.3);font-size:12px}
  .legend i{display:inline-block;width:12px;height:12px;margin-right:5px}
</style></head><body>
<div class="bar">
  <b>Capital · abrangência estimada (setor → escola + próxima)</b>
  <button data-cargo="dep" class="on" onclick="selc('dep')">Dep. Federal</button>
  <button data-cargo="pres" onclick="selc('pres')">Presidente</button>
  <b style="margin-left:8px">Mostrar:</b>
  <button data-modo="ambos" class="on" onclick="selmodo('ambos')">Ambos</button>
  <button data-modo="dir" onclick="selmodo('dir')">Só Direita</button>
  <button data-modo="esq" onclick="selmodo('esq')">Só Esquerda</button>
  <span id="cont" style="color:#555;font-size:12px"></span>
  <a href="../mapas.html">← Mapas</a>
</div>
<div id="map"></div>
<script>
const FC=__FC__;
let cargo='dep', modo='ambos';
const map=L.map('map',{preferCanvas:true}).setView([-23.55,-46.63],11);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {attribution:'Tiles &copy; Esri',maxZoom:17}).addTo(map);
function pdirf(f){ return cargo==='dep'?f.properties.dep_pdir:f.properties.pres_pdir; }
function pesqf(f){ return cargo==='dep'?f.properties.dep_pesq:f.properties.pres_pesq; }
function vencedor(f){ const d=pdirf(f), e=pesqf(f); if(d==null||e==null) return null; return d>=e?'dir':'esq'; }
function shade(win,marg){ const t=Math.max(.18,Math.min(1,marg/40));
  if(win==='dir') return `rgb(${Math.round(207-199*t)},${Math.round(224-176*t)},${Math.round(242-135*t)})`;
  return `rgb(${Math.round(252-149*t)},${Math.round(211-211*t)},${Math.round(196-183*t)})`; }
function estilo(f){ const w=vencedor(f); if(!w) return {fillColor:'#ccc',weight:0,fillOpacity:.25};
  return {fillColor:shade(w,Math.abs(pdirf(f)-pesqf(f))),weight:0,fillOpacity:.82}; }
function mostrar(f){ const w=vencedor(f); if(!w) return false; if(modo==='ambos') return true; return w===modo; }
let layer=null;
function draw(){
  if(layer) map.removeLayer(layer);
  let n=0;
  layer=L.geoJSON(FC,{filter:f=>{const ok=mostrar(f); if(ok)n++; return ok;}, style:estilo,
    onEachFeature:(f,l)=>{const p=f.properties; const w=vencedor(f);
    l.bindPopup(`<b>Setor ${p.s}</b>${p.b?'<br>'+p.b:''}<br>`+
      (w?`<b style="color:${w==='dir'?'#08519c':'#a50f15'}">Venceu: ${w==='dir'?'DIREITA':'ESQUERDA'}</b><br>`:'')+
      `Dep.Fed — Dir ${p.dep_pdir==null?'-':p.dep_pdir+'%'} · Esq ${p.dep_pesq==null?'-':p.dep_pesq+'%'}<br>`+
      `Presid — Dir ${p.pres_pdir==null?'-':p.pres_pdir+'%'} · Esq ${p.pres_pesq==null?'-':p.pres_pesq+'%'}`);}
  }).addTo(map);
  const el=document.getElementById('cont'); if(el) el.textContent=n.toLocaleString('pt-BR')+' setores';
}
function selc(c){cargo=c;document.querySelectorAll('[data-cargo]').forEach(b=>b.classList.toggle('on',b.dataset.cargo===c));draw();}
function selmodo(m){modo=m;document.querySelectorAll('[data-modo]').forEach(b=>b.classList.toggle('on',b.dataset.modo===m));draw();}
draw();
const lg=L.control({position:'bottomright'});
lg.onAdd=function(){const d=L.DomUtil.create('div','legend');
  d.innerHTML='<b>Quem teve mais votos</b><br><i style="background:#08306b"></i> Direita venceu<br>'+
    '<i style="background:#67000d"></i> Esquerda venceu<br>'+
    '<span style="color:#666">tom mais escuro = maior margem<br>setor → escola + próxima (estimativa)</span>';return d;};
lg.addTo(map);
</script></body></html>"""


if __name__ == "__main__":
    sys.exit(main())
