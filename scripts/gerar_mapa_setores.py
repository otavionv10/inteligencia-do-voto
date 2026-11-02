#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_mapa_setores.py
FUNCAO    : Etapa 3 - mapa por SETOR CENSITARIO (a menor malha oficial do IBGE).
            Agrega o voto de cada escola no seu setor (cnefe_cod_setor) e pinta
            o choropleth dos setores que contem local de votacao, cor por % direita.
            Geometria simplificada; GeoJSON embutido; alterna Dep.Federal/Presidente.
FONTES    : data/db/sao_paulo.duckdb (fact_votacao_secao + vw_candidato_campo)
            data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv (local -> cod_setor)
            D:/dados_cnefe/SP_setores_CD2022.gpkg (poligonos)
SAIDA     : data/analise/mapa_setores_voto.html
USO       : python _scripts/gerar_mapa_setores.py [ano]
"""
import json
import sys
from pathlib import Path

import duckdb

ANALISE = Path(r"D:/Dados_TSE/data/analise")
DB = "D:/Dados_TSE/data/db/sao_paulo.duckdb"
GPKG = "D:/dados_cnefe/SP_setores_CD2022.gpkg"
TOL = 0.0003  # simplificacao ~30 m


def main():
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    src = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    con = duckdb.connect(DB, read_only=True)
    con.execute("INSTALL spatial; LOAD spatial;")

    # local -> cod_setor (15 digitos)
    con.execute(f"""
        CREATE TEMP TABLE loc_setor AS
        SELECT cd_municipio_tse,
               TRY_CAST(nr_zona AS INTEGER) AS nr_zona,
               TRY_CAST(nr_local_votacao AS INTEGER) AS nr_local,
               left(regexp_replace(CAST(cnefe_cod_setor AS VARCHAR), '[^0-9]', '', 'g'), 15) AS cod_setor
          FROM read_csv('{src.as_posix()}', delim=';', header=true, all_varchar=true)
         WHERE cnefe_cod_setor IS NOT NULL AND cnefe_cod_setor <> ''
    """)

    # votos por local (dep 1T e pres 2T num passe so)
    con.execute(f"""
        CREATE TEMP TABLE vloc AS
        SELECT v.cd_municipio_tse, v.nr_zona, v.nr_local_votacao,
          SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='DIREITA')  dep_dir,
          SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND c.campo='ESQUERDA') dep_esq,
          SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='DEPUTADO FEDERAL' AND v.nr_turno=1 AND v.nr_votavel NOT IN (95,96,97)) dep_val,
          SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='DIREITA')  pres_dir,
          SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND c.campo='ESQUERDA') pres_esq,
          SUM(v.qt_votos) FILTER (WHERE UPPER(v.ds_cargo)='PRESIDENTE' AND v.nr_turno=2 AND v.nr_votavel NOT IN (95,96,97)) pres_val
        FROM fact_votacao_secao v
        LEFT JOIN vw_candidato_campo c ON c.ano_eletivo=v.ano_eletivo AND c.sq_candidato=v.sq_candidato
       WHERE v.ano_eletivo={ano}
       GROUP BY 1,2,3
    """)

    # agrega por setor
    con.execute("""
        CREATE TEMP TABLE vsetor AS
        SELECT s.cod_setor,
               SUM(COALESCE(vloc.dep_dir,0)) dep_dir, SUM(COALESCE(vloc.dep_esq,0)) dep_esq, SUM(COALESCE(vloc.dep_val,0)) dep_val,
               SUM(COALESCE(vloc.pres_dir,0)) pres_dir, SUM(COALESCE(vloc.pres_esq,0)) pres_esq, SUM(COALESCE(vloc.pres_val,0)) pres_val,
               count(DISTINCT (s.cd_municipio_tse,s.nr_zona,s.nr_local)) n_locais
          FROM loc_setor s
          JOIN vloc ON vloc.cd_municipio_tse=s.cd_municipio_tse AND vloc.nr_zona=s.nr_zona
                   AND vloc.nr_local_votacao=s.nr_local
         WHERE s.cod_setor <> ''
         GROUP BY 1
    """)
    n = con.execute("SELECT count(*) FROM vsetor").fetchone()[0]
    print(f"setores com voto: {n:,}")

    # junta poligonos (simplificados) + monta GeoJSON
    con.execute(f"""
        CREATE TEMP TABLE poly AS
        SELECT CAST(CD_SETOR AS VARCHAR) cod_setor, NM_MUN municipio, NM_BAIRRO bairro,
               ST_AsGeoJSON(ST_Simplify(geom,{TOL})) gj
          FROM ST_Read('{GPKG}')
    """)
    rows = con.execute("""
        SELECT p.cod_setor, p.municipio, p.bairro, p.gj,
               v.dep_dir, v.dep_esq, v.dep_val, v.pres_dir, v.pres_esq, v.pres_val, v.n_locais
          FROM vsetor v JOIN poly p USING (cod_setor)
    """).fetchall()
    print(f"setores casados com poligono: {len(rows):,}")

    feats = []
    for cod, mun, bairro, gj, dd, de, dv, pd_, pe, pv, nl in rows:
        try:
            geom = json.loads(gj)
        except Exception:
            continue
        pdir = round(100.0*dd/dv, 1) if dv else None
        pdesq = round(100.0*de/dv, 1) if dv else None
        ppres = round(100.0*pd_/pv, 1) if pv else None
        ppesq = round(100.0*pe/pv, 1) if pv else None
        feats.append({"type": "Feature", "geometry": geom, "properties": {
            "s": cod, "m": mun, "b": bairro or "", "nl": nl,
            "dep_pdir": pdir, "dep_pesq": pdesq, "dep_vdir": dd, "dep_vesq": de,
            "pres_pdir": ppres, "pres_pesq": ppesq, "pres_vdir": pd_, "pres_vesq": pe}})
    fc = {"type": "FeatureCollection", "features": feats}

    out = ANALISE / "mapa_setores_voto.html"
    out.write_text(PAGE.replace("__FC__", json.dumps(fc, ensure_ascii=False)), encoding="utf-8")
    mb = out.stat().st_size/1048576
    print(f"OK: {out}  ({mb:.1f} MB, {len(feats):,} setores)")
    return 0


PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapa por Setor Censitário — Voto SP</title>
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
  <b>Setor censitário · quem venceu</b>
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
const map=L.map('map',{preferCanvas:true}).setView([-22.9,-47.1],9);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {attribution:'Tiles &copy; Esri',maxZoom:16}).addTo(map);
function pdirf(f){ return cargo==='dep'?f.properties.dep_pdir:f.properties.pres_pdir; }
function pesqf(f){ return cargo==='dep'?f.properties.dep_pesq:f.properties.pres_pesq; }
function vencedor(f){ const d=pdirf(f), e=pesqf(f); if(d==null||e==null) return null; return d>=e?'dir':'esq'; }
// tom mais escuro = maior margem (0..40 pts)
function shade(win,marg){ const t=Math.max(.18,Math.min(1,marg/40));
  if(win==='dir') return `rgb(${Math.round(207-199*t)},${Math.round(224-176*t)},${Math.round(242-135*t)})`;
  return `rgb(${Math.round(252-149*t)},${Math.round(211-211*t)},${Math.round(196-183*t)})`; }
function estilo(f){ const w=vencedor(f); if(!w) return {fillColor:'#ccc',weight:.2,color:'#bbb',fillOpacity:.3};
  const marg=Math.abs(pdirf(f)-pesqf(f));
  return {fillColor:shade(w,marg),weight:.25,color:'#777',fillOpacity:.82}; }
function mostrar(f){ const w=vencedor(f); if(!w) return false; if(modo==='ambos') return true; return w===modo; }
let layer=null;
function draw(){
  if(layer) map.removeLayer(layer);
  let n=0;
  layer=L.geoJSON(FC,{filter:f=>{const ok=mostrar(f); if(ok)n++; return ok;}, style:estilo,
    onEachFeature:(f,l)=>{const p=f.properties; const w=vencedor(f);
      l.bindPopup(`<b>Setor ${p.s}</b><br>${p.m}${p.b?' - '+p.b:''}<br>Locais: ${p.nl}<br>`+
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
    '<span style="color:#666">tom mais escuro = maior margem<br>setores com local de votação</span>';return d;};
lg.addTo(map);
</script></body></html>"""


if __name__ == "__main__":
    sys.exit(main())
