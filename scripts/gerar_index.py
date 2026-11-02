#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ARQUIVO   : _scripts/gerar_index.py
FUNCAO    : Gera data/analise/index.html — a central de navegação de TODOS
            os artefatos de análise (Brasil + São Paulo), lendo o diretório
            em vez de lista manual (evita itens esquecidos).
SECOES    : 1. Brasil - Destaques (mapas nacionais)
              2. Brasil - Dashboards por UF (presidente/depfederal/governador)
              3. Brasil - Mapas por estado (choropleth)
              4. Brasil - Relatórios socioeleitorais
              5. Brasil - Rankings por estado (CSV zipado? nao: pastas)
              6. São Paulo - Mapas e dashboards históricos
              7. São Paulo - Planilhas TOP
SAIDA     : data/analise/index.html
USO       : python _scripts/gerar_index.py
Criado    : 2026-09-28
=============================================================================
"""
import glob
import sys
from pathlib import Path

ANALISE = Path(__file__).resolve().parent.parent / "data" / "analise"

HEAD = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Análise Eleitoral Brasil — TSE · Índice</title>
<style>
  :root{
    --bg:#f6f7f9; --card:#fff; --ink:#1a1a1a; --sub:#666; --line:#e3e6ea;
    --accent:#2d6cdf; --dir:#2166ac; --esq:#b2182b; --shadow:0 1px 3px rgba(0,0,0,.08);
  }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#161719; --card:#1f2124; --ink:#eaeaea; --sub:#9aa0a6; --line:#33363b;
           --accent:#5b8def; --shadow:0 1px 3px rgba(0,0,0,.4); }
  }
  *{box-sizing:border-box}
  body{ font-family:system-ui,"Segoe UI",Arial,sans-serif; margin:0; background:var(--bg);
        color:var(--ink); line-height:1.45; }
  .wrap{ max-width:1180px; margin:0 auto; padding:32px 20px 60px; }
  header h1{ font-size:26px; margin:0 0 6px; }
  header .sub{ color:var(--sub); font-size:14px; margin-bottom:4px; }
  header .meta{ color:var(--sub); font-size:12.5px; }
  section{ margin-top:34px; }
  section > h2{ font-size:15px; text-transform:uppercase; letter-spacing:.06em;
                color:var(--sub); margin:0 0 14px; padding-bottom:8px; border-bottom:1px solid var(--line); }
  .grid{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:14px; }
  .grid.slim{ grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); }
  a.card{ display:block; text-decoration:none; color:inherit; background:var(--card);
          border:1px solid var(--line); border-radius:12px; padding:16px 18px; box-shadow:var(--shadow);
          transition:transform .12s ease, border-color .12s ease, box-shadow .12s ease; }
  a.card:hover{ transform:translateY(-2px); border-color:var(--accent);
                box-shadow:0 6px 18px rgba(45,108,223,.16); }
  .card .tag{ display:inline-block; font-size:11px; font-weight:600; padding:2px 8px; border-radius:20px;
              background:rgba(45,108,223,.12); color:var(--accent); margin-bottom:10px; }
  .card.hero{ border-color:var(--accent); border-width:2px; }
  .card.hero .tag{ background:var(--accent); color:#fff; }
  .card h3{ font-size:15px; margin:0 0 6px; }
  .card p{ font-size:13px; color:var(--sub); margin:0; }
  .card .go{ font-size:13px; color:var(--accent); font-weight:600; margin-top:10px; display:inline-block; }
  .card.soon{ opacity:.62; pointer-events:none; border-style:dashed; }
  .card.soon .tag{ background:rgba(150,150,150,.15); color:var(--sub); }
  .card.soon .go{ color:var(--sub); }
  footer{ margin-top:44px; padding-top:18px; border-top:1px solid var(--line);
          color:var(--sub); font-size:12.5px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Análise Eleitoral — Brasil e São Paulo</h1>
    <div class="sub">Dados públicos e territoriais do TSE + IBGE · campo Direita × Esquerda por UF / Município / Zona / Seção / Local</div>
    <div class="meta">Índice central de painéis, mapas e relatórios · gerado por _scripts/gerar_index.py</div>
  </header>
"""

FOOT = r"""
  <footer>
    Projeto de análise eleitoral BR/SP · DuckDB + Python · dados agregados pós-LGPD (sem eleitores identificáveis).<br>
    Índice gerado automaticamente — rode <code>python _scripts/gerar_index.py</code> após gerar novos artefatos.
  </footer>
</div>
</body>
</html>"""


def card(href, tag, title, desc, hero=False):
    cls = "card hero" if hero else "card"
    return (f'      <a class="{cls}" href="{href}">\n'
            f'        <span class="tag">{tag}</span>\n'
            f'        <h3>{title}</h3>\n'
            f'        <p>{desc}</p>\n'
            f'        <span class="go">Abrir →</span>\n'
            f'      </a>')


def sec(title):
    return f'  <section>\n    <h2>{title}</h2>\n    <div class="grid">'


def sec_end():
    return '    </div>\n  </section>'


def main():
    out = [HEAD]

    # ---------- 1. Brasil - destaques ----------
    out.append(sec("Brasil — Destaques"))
    out.append(card("mapa_local_nacional_2022.html", "Mapa nacional", 
                    "Mapa — Locais de votação 2022 (BR)",
                    "92.427 locais com coordenada nas 27 UFs. Pinos por local (cluster), cor por vencedor do bloco. "
                    "Presidente (2T) / Dep. Federal (1T) / Governador. Filtro UF/cargo/tipo/município + Modo grafo.", hero=True))
    out.append(card("mapa_nacional_uf.html", "Mapa nacional",
                    "Mapa — Campo por UF",
                    "Choropleth Brasil por estado (27 UFs), % Direita/Esquerda por UF em 2022."))
    out.append(sec_end())

    # ---------- 1b. Brasil - indices e analises por local ----------
    out.append(sec("Brasil — Índices de campanha e análises por local"))
    out.append(card("mapa_indice_prioridade_presidente_2022.html", "Índice",
                    "Índice de Prioridade — Presidente 2022",
                    "Ação de campanha por local (Base/Mobilização/Persuasão/Hostil). Presidente 2T, 91.461 locais."))
    out.append(card("mapa_indice_prioridade_governador_2022.html", "Índice",
                    "Índice de Prioridade — Governador 2022",
                    "Ação de campanha por local. Governador (turno decisivo por UF), 91.461 locais."))
    out.append(card("mapa_indice_prioridade_depfederal_2022.html", "Índice",
                    "Índice de Prioridade — Dep. Federal 2022",
                    "Ação de campanha por local. Dep. Federal 1T, 91.461 locais."))
    out.append(card("mapa_rachadura_voto_2022.html", "Análise",
                    "Rachadura de voto 2022",
                    "Locais que trocam de lado entre Presidente/Governador/Dep.Federal. 91.461 locais."))
    out.append(card("mapa_trajetoria_presidente_2014_2022.html", "Análise",
                    "Trajetória Presidente 2014 → 2022",
                    "Perfis de movimento do voto por local (3 eleições). 71.550 locais."))
    out.append(card("grafico_tendencia.html", "Gráfico",
                    "Tendência de voto por cidade",
                    "Linha 2014→2018→2022 por município (Presidente 2T e Dep.Federal). 5.570 municípios."))
    out.append(sec_end())

    # ---------- 2. Brasil - dashboards por UF ----------
    ufs = sorted({Path(p).stem.split("_")[-1] for p in glob.glob(str(ANALISE / "dashboard_*.html"))})
    for cargo, label in (("presidente", "Presidente (2T)"), ("depfederal", "Dep. Federal (1T)"),
                         ("governador", "Governador (2T/1T)")):
        out.append(sec(f"Brasil — Dashboards {label} por UF"))
        for uf in ufs:
            f = ANALISE / f"dashboard_{cargo}_{uf}.html"
            if f.exists():
                out.append(card(f.name, uf, f"Dashboard — {uf}",
                                f"Município / Zona / Seção · campo Direita × Esquerda · 2014/18/22."))
        out.append(sec_end())

    # ---------- 3. Brasil - mapas por estado ----------
    out.append(sec("Brasil — Mapas por estado (choropleth por município)"))
    for f in sorted(glob.glob(str(ANALISE / "mapa_estado_*.html"))):
        uf = Path(f).stem.split("_")[-1]
        out.append(card(Path(f).name, uf, f"Mapa — {uf}",
                        f"Choropleth por município · campo político · 2022."))
    out.append(sec_end())

    # ---------- 4. Brasil - relatorios socio ----------
    out.append(sec("Brasil — Relatórios socioeleitorais por UF (2022)"))
    rels = sorted(glob.glob(str(ANALISE / "socio_uf" / "relatorio_socio_*.html")))
    for f in rels:
        uf = Path(f).stem.split("_")[-1]
        rel = Path("socio_uf") / Path(f).name
        out.append(card(rel.as_posix(), uf, f"Socio — {uf}",
                        "Abstenção · perfil do eleitorado · voto × indicadores (IBGE) · correlações."))
    folders = sorted({p.parent.name for p in ANALISE.glob("socio_uf/*/01_abstencao_*.csv")})
    for uf in folders:
        out.append(card(f"socio_uf/{uf}/01_abstencao_{uf}.csv", uf, f"Abstenção {uf} (CSV)",
                        "Tabela de abstenção por cargo/turno (2022)."))
    out.append(sec_end())

    # ---------- 5. Brasil - rankings ----------
    out.append(sec("Brasil — Rankings por estado (seções/zonas, CSV)"))
    for uf in sorted(p.name for p in (ANALISE / "ranking_estados").iterdir() if p.is_dir()):
        n = len(list((ANALISE / "ranking_estados" / uf).glob("*.csv")))
        out.append(card(f"ranking_estados/{uf}/", uf, f"Rankings — {uf}",
                        f"{n} arquivos (zona/seção) presidente, dep. federal, governador — direita/esquerda, % e total."))
    out.append(sec_end())

    # ---------- 6. SP - mapas e dashboards ----------
    out.append(sec("São Paulo — Mapas e dashboards (histórico)"))
    for f, tag, t, d in [
        ("dashboard_presidente_SP.html", "Dashboard", "Presidente SP",
         "Tabela por Estado/Cidade/Zona/Seção, 2014/18/22 (2T)."),
        ("dashboard_depfederal_SP.html", "Dashboard", "Dep. Federal SP",
         "Tabela por Estado/Cidade/Zona/Seção, 2014/18/22 (1T)."),
        ("mapa_calor_cidade_presidente.html", "Mapa", "Presidente por cidade (SP)",
         "Choropleth 645 cidades, % DIR/ESQ/votos/vencedor."),
        ("mapa_calor_cidade_depfederal.html", "Mapa", "Dep. Federal por cidade (SP)",
         "Choropleth 645 cidades, 2014/18/22 (1T)."),
        ("mapa_calor_zonas.html", "Mapa", "Zonas por direita/esquerda (SP)",
         "393 zonas no centróide dos locais, Pres 2T e DepFed 1T (2022)."),
        ("mapa_escolas_zonas.html", "Mapa · pinos",
         "Escolas, zonas e relevo (SP)",
         "10.845 locais em pinos (cluster) + relevo por zona. Modo grafo."),
        ("mapa_voto_local_2022.html", "Mapa por local", "Voto por local 2022 (SP)",
         "Distribuição do voto por local de votação — Governador SP 2022 (1T)."),
        ("mapa_setores_voto.html", "Mapa · setor", "Voto por setor censitário (SP)",
         "Choropleth na menor malha IBGE (8.911 setores), Dep Fed/Presidente."),
        ("mapa_catchment_capital.html", "Mapa · catchment", "Catchment por setor (capital)",
         "Áreas de captação por setor censitário na capital paulista."),
        ("mapa_catchment_capital.html", "Mapa · catchment", "Capital cheio (abrangência)",
         "27.299 setores da capital pela escola mais próxima, sem vazios."),
    ]:
        p = ANALISE / f
        if p.exists():
            out.append(card(f, tag, t, d))
    out.append(sec_end())

    # ---------- 7. SP - planilhas TOP ----------
    out.append(sec("São Paulo — Planilhas TOP (com endereços)"))
    for f in sorted(glob.glob(str(ANALISE / "*.xlsx"))):
        out.append(card(Path(f).name, "Planilha", Path(f).stem,
                        "Planilha Excel com top rankings e endereços."))
    out.append(sec_end())

    out.append(FOOT)
    html = "\n".join(out) + "\n"
    dest = ANALISE / "index.html"
    dest.write_text(html, encoding="utf-8")
    print(f"OK: {dest}  ({dest.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())