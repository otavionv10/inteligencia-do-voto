#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exporta o RESULTADO (campo politico ESQ/CEN/DIR) para MySQL e PostgreSQL.

Le os 6 CSVs de campo por SECAO (presidente 2014/18/22 + dep federal 2014/18/22)
e gera 3 tabelas prontas p/ site:
  resultado_secao   - 1 linha por (cargo,ano,turno,secao)
  resultado_cidade  - agregado por municipio  (645)
  resultado_estado  - agregado estado SP

Schema MySQL (usa AUTO_INCREMENT). Postgres troca p/ SERIAL/BIGSERIAL.
Escrita em batches para importacao cursorial.
"""
import csv
import os

SITE_DIR = r"D:/Dados_TSE/data/site_export"
os.makedirs(SITE_DIR, exist_ok=True)

ARQ = [
    ("PRESIDENTE", 2014, "campo_presidente_2014_por_secao.csv"),
    ("PRESIDENTE", 2018, "campo_presidente_2018_por_secao.csv"),
    ("PRESIDENTE", 2022, "campo_presidente_2022_por_secao.csv"),
    ("DEPFED",     2014, "campo_depfederal_2014_por_secao.csv"),
    ("DEPFED",     2018, "campo_depfederal_2018_por_secao.csv"),
    ("DEPFED",     2022, "campo_depfederal_2022_por_secao.csv"),
]

def ler():
    """Retorna listas (secao, cidade, estado) ja agregadas."""
    secao = []
    cidade = {}
    estado = {}
    for cargo, ano, fn in ARQ:
        p = os.path.join(r"D:/Dados_TSE/data/analise", fn)
        with open(p, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f, delimiter=";")
            for r in rd:
                turno = int(r["nr_turno"])
                mc = int(r["cd_municipio_tse"])
                secao.append((
                    cargo, ano, turno, mc,
                    int(r["nr_zona"]), int(r["nr_secao"]),
                    int(r["vot_esq"]), int(r["vot_cen"]), int(r["vot_dir"]),
                    int(r["validos"]),
                    float(r["share_esq"] or 0), float(r["share_cen"] or 0), float(r["share_dir"] or 0),
                    r["vencedor_campo"], r["nm_municipio_tse"],
                ))
                k = (cargo, ano, turno, mc)
                c = cidade.get(k)
                if c is None:
                    c = [cargo, ano, turno, mc, r["nm_municipio_tse"], 0, 0, 0, 0]
                    cidade[k] = c
                c[5] += int(r["vot_esq"]); c[6] += int(r["vot_cen"])
                c[7] += int(r["vot_dir"]); c[8] += int(r["validos"])
                e = estado.get((cargo, ano, turno))
                if e is None:
                    e = [cargo, ano, turno, 0, 0, 0, 0]
                    estado[(cargo, ano, turno)] = e
                e[3] += int(r["vot_esq"]); e[4] += int(r["vot_cen"])
                e[5] += int(r["vot_dir"]); e[6] += int(r["validos"])
    corpo_cidade = []
    for (cargo, ano, turno, mc), c in sorted(cidade.items()):
        es, cen, di, val = c[5], c[6], c[7], c[8]
        corpo_cidade.append((
            c[0], c[1], c[2], c[3], c[4], es, cen, di, val,
            round(100 * es / val, 2) if val else 0, round(100 * cen / val, 2) if val else 0,
            round(100 * di / val, 2) if val else 0,
            max(("ESQUERDA", "CENTRO", "DIREITA"), key=lambda x: dict(ESQUERDA=es, CENTRO=cen, DIREITA=di)[x]),
        ))
    corpo_estado = []
    for (cargo, ano, turno), e in sorted(estado.items()):
        es, cen, di, val = e[3], e[4], e[5], e[6]
        corpo_estado.append((
            e[0], e[1], e[2], es, cen, di, val,
            round(100 * es / val, 2) if val else 0, round(100 * cen / val, 2) if val else 0,
            round(100 * di / val, 2) if val else 0,
            max(("ESQUERDA", "CENTRO", "DIREITA"), key=lambda x: dict(ESQUERDA=es, CENTRO=cen, DIREITA=di)[x]),
        ))
    return secao, corpo_cidade, corpo_estado

DDL = {
    "secao": """CREATE TABLE IF NOT EXISTS resultado_secao (
  id       {pk} NOT NULL,
  cargo    VARCHAR(12)  NOT NULL,
  ano      SMALLINT     NOT NULL,
  turno    SMALLINT     NOT NULL,
  cd_municipio_tse INT NOT NULL,
  nr_zona  INT NOT NULL,
  nr_secao INT NOT NULL,
  vot_esq  INT NOT NULL,
  vot_cen  INT NOT NULL,
  vot_dir  INT NOT NULL,
  validos  INT NOT NULL,
  share_esq DECIMAL(6,2) NOT NULL,
  share_cen DECIMAL(6,2) NOT NULL,
  share_dir DECIMAL(6,2) NOT NULL,
  vencedor_campo VARCHAR(9)  NOT NULL,
  nm_municipio_tse VARCHAR(120) NOT NULL,
  PRIMARY KEY (id){extra}
);""",
    "cidade": """CREATE TABLE IF NOT EXISTS resultado_cidade (
  cargo   VARCHAR(12) NOT NULL,
  ano     SMALLINT    NOT NULL,
  turno   SMALLINT    NOT NULL,
  cd_municipio_tse INT NOT NULL,
  nm_municipio_tse VARCHAR(120) NOT NULL,
  vot_esq INT NOT NULL, vot_cen INT NOT NULL, vot_dir INT NOT NULL, validos INT NOT NULL,
  share_esq DECIMAL(6,2) NOT NULL, share_cen DECIMAL(6,2) NOT NULL, share_dir DECIMAL(6,2) NOT NULL,
  vencedor_campo VARCHAR(9) NOT NULL,
  PRIMARY KEY (cargo, ano, turno, cd_municipio_tse){extra}
);""",
    "estado": """CREATE TABLE IF NOT EXISTS resultado_estado (
  cargo  VARCHAR(12) NOT NULL,
  ano    SMALLINT    NOT NULL,
  turno  SMALLINT    NOT NULL,
  vot_esq INT NOT NULL, vot_cen INT NOT NULL, vot_dir INT NOT NULL, validos INT NOT NULL,
  share_esq DECIMAL(6,2) NOT NULL, share_cen DECIMAL(6,2) NOT NULL, share_dir DECIMAL(6,2) NOT NULL,
  vencedor_campo VARCHAR(9) NOT NULL,
  PRIMARY KEY (cargo, ano, turno){extra}
);""",
}

def fmt(v):
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)

def escreve(dial, secao, cid, est):
    if dial == "mysql":
        pk, extra = "BIGINT AUTO_INCREMENT", ""
    else:
        pk, extra = "BIGINT GENERATED ALWAYS AS IDENTITY", ", UNIQUE (id)"
    with open(os.path.join(SITE_DIR, f"site_resultado_{dial}.sql"), "w", encoding="utf-8") as f:
        f.write(f"-- Campo politico TSE (ESQUERDA/CENTRO/DIREITA) - SP 2014/18/22\n")
        f.write(f"-- gerado por exportar_site_sql.py | {len(secao):,} secoes\n")
        f.write("BEGIN;\n\n" if dial == "postgres" else "START TRANSACTION;\n\n")
        for nome, col in (("secao", secao), ("cidade", cid), ("estado", est)):
            f.write(DDL[nome].format(pk=pk, extra=extra) + "\n")
            if nome == "secao":
                f.write("CREATE INDEX IF NOT EXISTS idx_res_geo ON resultado_secao"
                        " (cargo, ano, turno, cd_municipio_tse, nr_zona);\n\n")
            cols = ("cargo,ano,turno,cd_municipio_tse,nr_zona,nr_secao,vot_esq,vot_cen,vot_dir,"
                    "validos,share_esq,share_cen,share_dir,vencedor_campo,nm_municipio_tse") if nome == "secao" \
                else ("cargo,ano,turno,cd_municipio_tse,nm_municipio_tse,vot_esq,vot_cen,vot_dir,"
                      "validos,share_esq,share_cen,share_dir,vencedor_campo") if nome == "cidade" \
                else "cargo,ano,turno,vot_esq,vot_cen,vot_dir,validos,share_esq,share_cen,share_dir,vencedor_campo"
            f.write(f"INSERT INTO resultado_{nome} ({cols}) VALUES\n")
            B = 500
            for i in range(0, len(col), B):
                bloco = col[i:i + B]
                linhas = []
                for r in bloco:
                    txt = ",".join(fmt(x) for x in r)
                    linhas.append("(" + txt + ")")
                f.write(",\n".join(linhas))
                f.write(";\n" if i + B >= len(col) else ",\n")
            f.write("\n")
        f.write("COMMIT;\n" if dial == "postgres" else "COMMIT;\n")

if __name__ == "__main__":
    secao, cid, est = ler()
    print(f"secoes={len(secao):,} cidades={len(cid):,} estados={len(est):,}")
    escreve("mysql", secao, cid, est)
    escreve("postgres", secao, cid, est)
    for f in os.listdir(SITE_DIR):
        p = os.path.join(SITE_DIR, f)
        print(f"{os.path.getsize(p)/1e6:7.2f} MB  {f}")