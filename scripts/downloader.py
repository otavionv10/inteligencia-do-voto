"""
=============================================================================
ARQUIVO   : _scripts/downloader.py
FUNCAO    : Baixa o manifest completo do TSE (retomavel por Range + sha256)
DEPENDE   : curl_cffi (impersonate chrome124), common.py
USO       : python _scripts/downloader.py [--only chave1,chave2] [--force] [--workers N]
CRIADO    : 2026-09-20
ALTERADO  : 2026-09-20 - criacao
=============================================================================
"""
import argparse
import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from common import (RAW_DIR, ENCODING, IMPERSONATE, ensure_dirs,
                    load_manifest, load_state, save_state)

from curl_cffi import requests as cr


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_one(item: dict, state: dict, force: bool, session, verb) -> str:
    """Baixa um arquivo. Retorna mensagem de status."""
    key = item["key"]
    dest = RAW_DIR / item["local"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")

    known = state.get(key, {})
    if dest.exists() and not force:
        h = _hash_file(dest)
        if known.get("sha256") == h:
            return f"OK(skip) {key}  {dest.name}"
        return f"OK(reverificado) {key} (hash antigo diferente, hash atual {h[:12]}...)"

    url = item["url"]
    last_err = None
    for attempt in range(1, 6):
        try:
            offset = part.stat().st_size if part.exists() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            r = cr.get(url, impersonate=IMPERSONATE, timeout=600,
                       headers=headers, stream=True)
            try:
                if r.status_code not in (200, 206):
                    raise RuntimeError(f"HTTP {r.status_code}")
                mode = "ab" if offset else "wb"
                with open(part, mode) as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
            finally:
                r.close()
            os_safe_rename(part, dest)
            h = _hash_file(dest)
            state[key] = {"sha256": h, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_state(state)
            return f"OK {key}  {dest.name}  sha256={h[:12]}..."
        except Exception as e:
            last_err = e
            verb(f"  retry {key} (tentativa {attempt}): {e!r}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"FALHOU {key}: {last_err!r}")


def os_safe_rename(src: Path, dst: Path):
    if dst.exists():
        dst.unlink()
    src.rename(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="keys separadas por virgula")
    ap.add_argument("--force", action="store_true", help="ignora checksum e rebaixa")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    ensure_dirs()
    items = load_manifest()
    if args.list:
        for it in items:
            print(f"{it['key']:24s} {it['tipo']:18s} {it['ano']}  {it['local']}")
        return

    if args.only:
        allow = {k.strip() for k in args.only.split(",") if k.strip()}
        items = [it for it in items if it["key"] in allow]

    state = load_state()
    print(f"{'='*80}\nDados TSE - download de {len(items)} arquivos\nOrigem : cdn.tse.jus.br (Akamai, bypass curl_cffi)\nDestino: {RAW_DIR}\n{'='*80}")

    ok = []
    errors = []
    if args.workers <= 1:
        session = cr.Session(impersonate=IMPERSONATE)
        for it in items:
            try:
                msg = download_one(it, state, args.force, session, print)
                print(msg)
                ok.append(it["key"])
            except Exception as e:
                print(f"  ERRO {e}", file=sys.stderr)
                errors.append(it["key"])
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(download_one, it, state, args.force,
                                 cr.Session(impersonate=IMPERSONATE), print): it["key"]
                       for it in items}
            for fut in as_completed(futures):
                k = futures[fut]
                try:
                    print(fut.result())
                    ok.append(k)
                except Exception as e:
                    print(f"  ERRO {e}", file=sys.stderr)
                    errors.append(k)

    print(f"\nConcluido: {len(ok)} ok, {len(errors)} falhas.")
    for e in errors:
        print("  FALHOU:", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()