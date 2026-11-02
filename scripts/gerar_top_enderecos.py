#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/gerar_top_enderecos.py
FUNCAO    : Excel em formato LONGO (1 linha por local/endereco) com 2 abas:
            "Top Direita" e "Top Esquerda", ordenadas pelos VOTOS ABSOLUTOS do
            cargo escolhido (presidente por padrao). Reaproveita o arquivo ja
            enriquecido com CNEFE (endereco/rua/bairro/CEP/tipo + votos da zona).
ENTRADA   : data/analise/enderecos_locais_zona_sp_{ano}_cnefe.csv
SAIDA     : data/analise/top_enderecos_{cargo}_sp_{ano}.xlsx
USO       : python _scripts/gerar_top_enderecos.py [presidente|depfederal] [ano]
"""
import csv
import sys
from pathlib import Path

ANALISE = Path(r"D:/Dados_TSE/data/analise")
PREFIXO = {"presidente": "pres", "presid": "pres", "pres": "pres",
           "depfederal": "dep", "deputado": "dep", "dep": "dep"}


def main():
    cargo = (sys.argv[1] if len(sys.argv) > 1 else "presidente").lower()
    ano = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
    pre = PREFIXO.get(cargo, "pres")
    rotulo = "Presidente" if pre == "pres" else "Deputado Federal"

    src = ANALISE / f"enderecos_locais_zona_sp_{ano}_cnefe.csv"
    if not src.exists():
        print(f"nao encontrei {src.name}; rode enriquecer_enderecos_cnefe.py antes")
        return 1
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig"), delimiter=";"))
    cols = list(rows[0].keys())

    def num(d, k):
        try:
            return int(d.get(k) or 0)
        except ValueError:
            return 0

    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    for aba, chave in (("Top Direita", f"{pre}_vot_dir"), ("Top Esquerda", f"{pre}_vot_esq")):
        ordenado = sorted(rows, key=lambda d: num(d, chave), reverse=True)
        ws = wb.create_sheet(aba)
        ws.append(cols)
        for d in ordenado:
            ws.append([d.get(c, "") for c in cols])
        ws.freeze_panes = "A2"
    out = ANALISE / f"TOP Escolas por Votos - {rotulo} (Direita e Esquerda) com Enderecos.xlsx"
    wb.save(out)
    print(f"OK: {out.name}  | abas {wb.sheetnames} | {len(rows):,} locais por aba")

    def a(s): return str(s).encode("ascii", "replace").decode()
    top = sorted(rows, key=lambda d: num(d, f"{pre}_vot_dir"), reverse=True)[:3]
    print(f"topo DIREITA ({rotulo}):")
    for d in top:
        print(f"  z{d['nr_zona']} {a(d['nm_municipio'])} | {a(d['nm_local_votacao'])[:26]} "
              f"| {pre}_vot_dir={d.get(pre+'_vot_dir')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
