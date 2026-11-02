"""
=============================================================================
ARQUIVO   : _scripts/common.py
FUNCAO    : Config e utilitarios compartilhados (download + carga)
DEPENDE   : python stdlib
DATA_DIR  : override via env TSE_DATA_DIR
CRIADO    : 2026-09-20
ALTERADO  : 2026-09-20 - criacao
=============================================================================
"""
import json
import os
from pathlib import Path

PROJETO = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("TSE_DATA_DIR", str(PROJETO / "data")))
RAW_DIR = DATA_DIR / "raw"
EXTRACTED_DIR = DATA_DIR / "extracted"
DB_DIR = DATA_DIR / "db"
IBGE_DIR = DATA_DIR / "ibge"

MANIFEST_PATH = Path(__file__).resolve().parent / "download_manifest.json"
STATE_PATH = DATA_DIR / "download_state.json"
DB_PATH = DB_DIR / "sao_paulo.duckdb"

IMPERSONATE = "chrome124"
ENCODING = "latin-1"
DELIMITER = ";"


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["files"]


def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def ensure_dirs():
    for d in (RAW_DIR, EXTRACTED_DIR, DB_DIR, IBGE_DIR):
        d.mkdir(parents=True, exist_ok=True)