#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/enriquecer_enderecos_cnefe.py
FUNCAO    : Enriquece o unpivot de enderecos dos locais com:
            (a) LOGRADOURO ESTRUTURADO do CNEFE (tipo/titulo/nome + setor),
                casando em 2 camadas: CEP+numero -> vizinho mais proximo por
                COORDENADA no mesmo municipio (combina variacoes de busca);
            (b) votos ABSOLUTOS de direita/esquerda da zona (dep e presid);
            e ORDENA por maior nr de votos de direita (Dep. Federal), depois local.
            Grava arquivo NOVO (_cnefe) p/ nao conflitar com Excel aberto.
ENTRADA   : data/analise/enderecos_locais_zona_sp_{ano}.csv
            data/analise/ranking_zonas_{depfederal,presidente}_{ano}_{t}t.csv
BANCOS    : ATTACH read-only sao_paulo.duckdb (TSE->IBGE) e sp_geo.duckdb (CNEFE)
SAIDAS    : data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv (+ .xlsx)
USO       : python _scripts/enriquecer_enderecos_cnefe.py [ano]
"""
import csv
import sys
from pathlib import Path

import duckdb

ANALISE = Path(r"D:/Dados_TSE/data/analise")
DB = "D:/Dados_TSE/data/db/sao_paulo.duckdb"
CNEFE = "D:/dados_cnefe/sp_geo.duckdb"
BBOX = 0.03  # ~3 km p/ o vizinho mais proximo por coordenada


def ler_ranking(nome):
    p = ANALISE / nome
    d = {}
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8-sig"), delimiter=";"):
            d[int(r["nr_zona"])] = r
    return d


def main():
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    src = ANALISE / f"enderecos_locais_zona_sp_{ano}.csv"
    if not src.exists():
        print(f"nao encontrei {src.name}; rode antes gerar_enderecos_locais.py")
        return 1

    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{DB}' AS tse (READ_ONLY)")
    con.execute(f"ATTACH '{CNEFE}' AS cnefe (READ_ONLY)")

    con.execute(f"""
        CREATE TEMP TABLE loc AS
        SELECT l.*,
               lpad(regexp_replace(CAST(l.nr_cep AS VARCHAR), '[^0-9]', '', 'g'), 8, '0') AS cep8,
               TRY_CAST(regexp_extract(CAST(l.numero AS VARCHAR), '\\d+', 0) AS INTEGER) AS num_int,
               TRY_CAST(m.cd_municipio_ibge AS INTEGER) AS ibge,
               TRY_CAST(l.lat AS DOUBLE) AS latd, TRY_CAST(l.lon AS DOUBLE) AS lond
          FROM read_csv('{src.as_posix()}', delim=';', header=true, all_varchar=true) l
          LEFT JOIN tse.dim_municipio m ON m.cd_municipio_tse = l.cd_municipio_tse
    """)
    n = con.execute("SELECT count(*) FROM loc").fetchone()[0]

    # camada 1: CEP + numero (exato -> mais proximo de numero)
    con.execute("""
        CREATE TEMP TABLE m_cep AS
        WITH cand AS (
          SELECT l.cd_municipio_tse, l.nr_zona, l.nr_local_votacao,
                 e.tipo_logradouro, e.titulo_logradouro, e.nome_logradouro,
                 e.num_endereco AS cnefe_numero, e.cod_setor AS cnefe_cod_setor,
                 CASE WHEN TRY_CAST(regexp_extract(e.num_endereco,'\\d+',0) AS INTEGER)=l.num_int
                      THEN 0 ELSE 1 END AS pri,
                 abs(coalesce(TRY_CAST(regexp_extract(e.num_endereco,'\\d+',0) AS INTEGER),0)
                     - coalesce(l.num_int,0)) AS dnum
            FROM loc l JOIN cnefe.enderecos e ON e.cep = l.cep8
        )
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               tipo_logradouro, titulo_logradouro, nome_logradouro,
               cnefe_numero, cnefe_cod_setor,
               CASE WHEN pri=0 THEN 'cep_num' ELSE 'cep_prox' END AS cnefe_match
          FROM cand
        QUALIFY row_number() OVER (PARTITION BY cd_municipio_tse, nr_zona, nr_local_votacao
                                   ORDER BY pri, dnum) = 1
    """)
    c1 = con.execute("SELECT count(*) FROM m_cep").fetchone()[0]

    # camada 2: vizinho mais proximo por COORDENADA (mesmo municipio), p/ quem faltou
    con.execute(f"""
        CREATE TEMP TABLE m_coord AS
        WITH falta AS (
          SELECT l.* FROM loc l
           WHERE l.latd IS NOT NULL AND l.ibge IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM m_cep x
                              WHERE x.cd_municipio_tse=l.cd_municipio_tse
                                AND x.nr_zona=l.nr_zona AND x.nr_local_votacao=l.nr_local_votacao)
        ),
        cand AS (
          SELECT f.cd_municipio_tse, f.nr_zona, f.nr_local_votacao,
                 e.tipo_logradouro, e.titulo_logradouro, e.nome_logradouro,
                 e.num_endereco AS cnefe_numero, e.cod_setor AS cnefe_cod_setor,
                 (e.lat-f.latd)*(e.lat-f.latd)+(e.lon-f.lond)*(e.lon-f.lond) AS d2
            FROM falta f JOIN cnefe.enderecos e
              ON e.codigo_ibge=f.ibge
             AND e.lat BETWEEN f.latd-{BBOX} AND f.latd+{BBOX}
             AND e.lon BETWEEN f.lond-{BBOX} AND f.lond+{BBOX}
        )
        SELECT cd_municipio_tse, nr_zona, nr_local_votacao,
               tipo_logradouro, titulo_logradouro, nome_logradouro,
               cnefe_numero, cnefe_cod_setor, 'coord_prox' AS cnefe_match
          FROM cand
        QUALIFY row_number() OVER (PARTITION BY cd_municipio_tse, nr_zona, nr_local_votacao
                                   ORDER BY d2) = 1
    """)
    c2 = con.execute("SELECT count(*) FROM m_coord").fetchone()[0]
    con.execute("CREATE TEMP TABLE m_all AS SELECT * FROM m_cep UNION ALL SELECT * FROM m_coord")
    tot = c1 + c2
    print(f"locais: {n:,} | logradouro CNEFE: CEP {c1:,} + coord {c2:,} = {tot:,} ({100*tot/n:.1f}%) "
          f"| ainda sem: {n-tot:,}")

    res = con.execute("""
        SELECT l.* EXCLUDE (cep8, num_int, ibge, latd, lond),
               m.tipo_logradouro   AS cnefe_tipo_logradouro,
               m.titulo_logradouro AS cnefe_titulo_logradouro,
               m.nome_logradouro   AS cnefe_nome_logradouro,
               m.cnefe_numero, m.cnefe_cod_setor,
               coalesce(m.cnefe_match, 'sem_cnefe') AS cnefe_match
          FROM loc l LEFT JOIN m_all m USING (cd_municipio_tse, nr_zona, nr_local_votacao)
    """)
    base_cols = [d[0] for d in res.description]
    rows = [dict(zip(base_cols, r)) for r in res.fetchall()]

    dep = ler_ranking(f"ranking_zonas_depfederal_{ano}_1t.csv")
    pres = ler_ranking(f"ranking_zonas_presidente_{ano}_2t.csv")
    for d in rows:
        z = int(d["nr_zona"]); dd, pp = dep.get(z, {}), pres.get(z, {})
        d["dep_vot_dir"] = dd.get("vot_dir", ""); d["dep_vot_esq"] = dd.get("vot_esq", "")
        d["pres_vot_dir"] = pp.get("vot_dir", ""); d["pres_vot_esq"] = pp.get("vot_esq", "")

    def kdir(d):
        try:
            return (-int(d["dep_vot_dir"] or 0), int(d["nr_local_votacao"]))
        except ValueError:
            return (0, 0)
    rows.sort(key=kdir)

    cols = base_cols + ["dep_vot_dir", "dep_vot_esq", "pres_vot_dir", "pres_vot_esq"]
    out_csv = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";", extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"OK: {out_csv.name}  ({len(rows):,} locais, ordenado por votos DIR do Dep.Federal)")

    try:
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "Enderecos_locais"
        ws.append(cols)
        for d in rows:
            ws.append([d.get(c, "") for c in cols])
        ws.freeze_panes = "A2"
        wb.save(ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.xlsx")
        print(f"OK: enderecos_locais_zona_sp_{ano}_cnefe.xlsx")
    except PermissionError:
        print("XLSX travado (aberto no Excel?); CSV gravado normalmente.")
    except ImportError:
        print("(openpyxl indisponivel; XLSX pulado)")

    def a(s): return str(s).encode("ascii", "replace").decode()
    from collections import Counter
    print("metodos:", dict(Counter(d["cnefe_match"] for d in rows)))
    print("\n=== amostra topo (mais votos DIR) ===")
    for d in rows[:5]:
        print(f"  z{d['nr_zona']} {a(d['nm_municipio'])} L{d['nr_local_votacao']} | "
              f"CNEFE '{a(d['cnefe_tipo_logradouro'])} {a(d['cnefe_nome_logradouro'])}' [{d['cnefe_match']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
