"""
=============================================================================
ARQUIVO   : _scripts/gerar_manifest_brasil.py
FUNCAO    : Estende download_manifest.json com os arquivos por UF do BRASIL
            inteiro (26 UFs alem de SP). Mantem os itens SP existentes intactos
            (chaves iguais -> reuso do hash em download_state, sem re-baixar).
FAMILIAS  : votacao_secao     (2012/14/16/18/20/22/24, por UF)
            perfil_eleitor_secao (2020/22/24/26, por UF)
USO       : python _scripts/gerar_manifest_brasil.py
=============================================================================
"""
import json
from pathlib import Path

BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
MANIFEST = Path(__file__).resolve().parent / "download_manifest.json"

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]

ANOS_VOTACAO = [2012, 2014, 2016, 2018, 2020, 2022, 2024]
ANOS_PERFIL = [2020, 2022, 2024, 2026]


def main():
    with open(MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    existing = manifest["files"]
    have_keys = {it["key"] for it in existing}
    added = []

    for ano in ANOS_VOTACAO:
        for uf in UFS:
            if uf == "SP":
                continue
            key = f"votacao_secao_{ano}_{uf}"
            if key in have_keys:
                continue
            added.append({
                "key": key,
                "local": f"votacao_secao/{ano}/votacao_secao_{ano}_{uf}.zip",
                "url": f"{BASE}/votacao_secao/votacao_secao_{ano}_{uf}.zip",
                "tipo": "votacao_secao",
                "ano": ano,
                "uf": uf,
            })

    for ano in ANOS_PERFIL:
        for uf in UFS:
            if uf == "SP":
                continue
            key = f"perfil_secao_{ano}_{uf}"
            if key in have_keys:
                continue
            added.append({
                "key": key,
                "local": f"eleitorado_secao/{ano}/perfil_eleitor_secao_{ano}_{uf}.zip",
                "url": f"{BASE}/perfil_eleitor_secao/perfil_eleitor_secao_{ano}_{uf}.zip",
                "tipo": "eleitorado_secao",
                "ano": ano,
                "uf": uf,
            })

    manifest["files"] = existing + added
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    est = len(added) * 90  # MB medio por zip (aprox)
    print(f"Manifest atualizado: {len(existing)} itens SP + {len(added)} novos UFs = {len(manifest['files'])}")
    print(f"Novos: votacao_secao={sum(1 for a in added if a['tipo']=='votacao_secao')}, "
          f"perfil={sum(1 for a in added if a['tipo']=='eleitorado_secao')}")
    print(f"Estimativa zips novos: ~{est/1024:.1f} GB (carga: ~{est*11/1024:.0f} GB extraido)")


if __name__ == "__main__":
    main()