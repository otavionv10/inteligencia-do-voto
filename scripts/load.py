"""
=============================================================================
ARQUIVO   : _scripts/load.py
FUNCAO    : ETL dos dados TSE -> DuckDB (extrai zips, normaliza encoding, carrega)
DEPENDE   : duckdb>=1.5, common.py, _sql/schema.sql
USO       :
   python _scripts/load.py               # tudo (extrai + carrega)
   python _scripts/load.py --only perfil # so eleitorado por secao
   python _scripts/load.py --extract     # so normaliza os zips (latin-1 -> utf-8)
CRIADO    : 2026-09-20
ALTERADO  : 2026-09-20 - criacao
=============================================================================
"""
import argparse
import sys
import zipfile
from pathlib import Path

from common import (RAW_DIR, EXTRACTED_DIR, DB_PATH, ENCODING,
                    ensure_dirs, load_manifest)

import duckdb


# ---------------------------------------------------------------------------
# 1. EXTRACAO + NORMALIZACAO (latin-1 -> utf-8)
# ---------------------------------------------------------------------------

def extract_csv(zip_path: Path, out_dir: Path, verbose=True) -> list[Path]:
    """Extrai todos os .csv do zip, decodificando latin-1 para utf-8."""
    out_dir.mkdir(parents=True, exist_ok=True)
    produced = []
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            if not member.endswith(".csv"):
                continue
            target = out_dir / Path(member).name
            if target.exists() and target.stat().st_size > 0:
                produced.append(target)
                continue
            tmp = target.with_suffix(".csv.tmp")
            with z.open(member) as src, open(tmp, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk.decode(ENCODING).encode("utf-8"))
            tmp.replace(target)
            produced.append(target)
            if verbose:
                print(f"  extraido: {member} -> {target}")
    return produced


def extract_all(manifest, verbose=True) -> dict:
    """Retorna {tipo_ano: [csv_paths]}."""
    result = {}
    for it in manifest:
        zip_path = RAW_DIR / it["local"]
        if not zip_path.exists():
            continue
        out_dir = EXTRACTED_DIR / it["tipo"] / str(it["ano"] or "geral")
        csvs = extract_csv(zip_path, out_dir, verbose)
        key = f"{it['tipo']}_{it['ano'] or 'geral'}"
        result[key] = csvs
    return result


# ---------------------------------------------------------------------------
# 2. HELPERS SQL
# ---------------------------------------------------------------------------

Q = lambda s: f'"{s}"'


def i(s):  # inteiro
    return f"CAST(NULLIF(TRIM({s}),'') AS INTEGER)"


def big(s):  # bigint
    return f"CAST(NULLIF(TRIM({s}),'') AS BIGINT)"


def dbl(s):  # double (virgula decimal -> ponto)
    return f"CAST(NULLIF(TRIM(REPLACE(REPLACE({s},',','.'),'\"','')),'') AS DOUBLE)"


def txt(s):
    return s


def read_csv(path: str):
    return (f"read_csv_auto('{path}', header=true, delim=';', "
            f"all_varchar=true, sample_size=-1, nullstr='', dateformat='%d/%m/%Y')")


def header_of(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        line = f.readline()
    return [c.strip().strip('"') for c in line.rstrip("\r\n").split(";")]


def exists(col: str, hdr: list[str]) -> bool:
    return col in hdr


def col_or_null(col: str, hdr: list[str], cast=txt):
    return cast(col) if exists(col, hdr) else "NULL"


# ---------------------------------------------------------------------------
# 3. CARGA
# ---------------------------------------------------------------------------

def load_municipio(con, csv_path):
    print("dim_municipio (mapa TSE<->IBGE)...")
    con.execute(f"""
        INSERT OR REPLACE INTO dim_municipio
        SELECT LPAD(CD_MUNICIPIO_TSE,5,'0'), NM_MUNICIPIO_TSE,
               LPAD(CD_MUNICIPIO_IBGE,7,'0'), SG_UF, NM_UF
        FROM {read_csv(csv_path)}
    """)


def load_secao_local(con, csvs, ano):
    """dim_secao + dim_local_votacao + fact_eleitorado_local (2022/2024/2026)."""
    sp = [c for c in csvs if "_SP.csv" in c.name]
    if not sp:
        sp = csvs
    if not sp:
        print("  AVISO: sem arquivo SP para local_votacao", ano)
        return
    path = str(sp[0])
    print(f"  carregando secao/local/eleitorado -> ano {ano} ...")
    con.execute(f"DELETE FROM dim_secao WHERE ano_eletivo = {ano}")
    con.execute(f"DELETE FROM dim_local_votacao WHERE ano_eletivo = {ano}")
    con.execute(f"DELETE FROM fact_eleitorado_local WHERE ano_eletivo = {ano}")

    r = read_csv(path)
    con.execute(f"""
        INSERT INTO dim_local_votacao
        SELECT {ano}, LPAD(CD_MUNICIPIO,5,'0'), {i('NR_ZONA')}, {i('NR_LOCAL_VOTACAO')},
               MAX(NM_LOCAL_VOTACAO), MAX(DS_TIPO_LOCAL), MAX(DS_ENDERECO),
               MAX(NM_BAIRRO), MAX(NR_CEP),
               MAX({dbl('NR_LATITUDE')}), MAX({dbl('NR_LONGITUDE')}),
               MAX({i('CD_SITU_LOCAL_VOTACAO')}), MAX(DS_SITU_LOCAL_VOTACAO)
        FROM {r}
        WHERE SG_UF='SP'
        GROUP BY CD_MUNICIPIO, NR_ZONA, NR_LOCAL_VOTACAO
    """)

    con.execute(f"""
        INSERT INTO dim_secao
        SELECT {ano}, LPAD(CD_MUNICIPIO,5,'0'), {i('NR_ZONA')}, {i('NR_SECAO')},
               MAX({i('CD_TIPO_SECAO_AGREGADA')}), MAX(DS_TIPO_SECAO_AGREGADA),
               MAX({i('NR_SECAO_PRINCIPAL')}),
               MAX({i('CD_SITU_SECAO')}), MAX(DS_SITU_SECAO),
               MAX({i('CD_SITU_SECAO_ACESSIBILIDADE')}), MAX(DS_SITU_SECAO_ACESSIBILIDADE)
        FROM {r}
        WHERE SG_UF='SP'
        GROUP BY CD_MUNICIPIO, NR_ZONA, NR_SECAO
    """)

    con.execute(f"""
        INSERT INTO fact_eleitorado_local
        SELECT {ano}, {i('NR_TURNO')}, LPAD(CD_MUNICIPIO,5,'0'),
               {i('NR_ZONA')}, {i('NR_SECAO')}, {i('NR_LOCAL_VOTACAO')},
               {big('QT_ELEITOR_SECAO')}, {big('QT_ELEITOR_ELEICAO_FEDERAL')},
               {big('QT_ELEITOR_ELEICAO_ESTADUAL')}, {big('QT_ELEITOR_ELEICAO_MUNICIPAL')}
        FROM {r}
        WHERE SG_UF='SP'
    """)


def load_perfil(con, csvs, ano):
    sp = [c for c in csvs if "_SP.csv" in c.name]
    if not sp:
        print("  AVISO: sem arquivo SP para perfil", ano)
        return
    path = str(sp[0])
    hdr = header_of(Path(path))
    ano_col = "AA_ELEICAO" if "AA_ELEICAO" in hdr else "ANO_ELEICAO"
    eleit_col = "QT_ELEITORES" if "QT_ELEITORES" in hdr and "QT_ELEITORES_PERFIL" not in hdr else "QT_ELEITORES_PERFIL"
    ns_col = "QT_ELEITORES_NOME_SOCIAL" if "QT_ELEITORES_NOME_SOCIAL" in hdr else "QT_ELEITORES_INC_NM_SOCIAL"

    sel = [
        f"{ano} AS ano_eletivo",
        f"NULL AS cd_eleicao",
        f"LPAD(CD_MUNICIPIO,5,'0') AS cd_municipio_tse",
        i("NR_ZONA") + " AS nr_zona",
        i("NR_SECAO") + " AS nr_secao",
        i("NR_LOCAL_VOTACAO") + " AS nr_local_votacao",
        txt("DS_GENERO") + " AS ds_genero",
        txt("DS_ESTADO_CIVIL") + " AS ds_estado_civil",
        txt("DS_GRAU_ESCOLARIDADE") + " AS ds_grau_escolaridade",
        txt("DS_FAIXA_ETARIA") + " AS ds_faixa_etaria",
        txt("DS_RACA_COR") + " AS ds_cor_raca",
        i("CD_IDENTIDADE_GENERO") + " AS cd_identidade_genero",
        txt("DS_IDENTIDADE_GENERO") + " AS ds_identidade_genero",
        i("CD_QUILOMBOLA") + " AS cd_quilombola",
        txt("DS_QUILOMBOLA") + " AS ds_quilombola",
        i("CD_INTERPRETE_LIBRAS") + " AS cd_interprete_libras",
        txt("DS_INTERPRETE_LIBRAS") + " AS ds_interprete_libras",
        col_or_null("TP_OBRIGATORIEDADE_VOTO", hdr) + " AS tp_obrigatoriedade_voto",
        i("CD_GENERO") + " AS cd_genero",
        i("CD_ESTADO_CIVIL") + " AS cd_estado_civil",
        i("CD_FAIXA_ETARIA") + " AS cd_faixa_etaria",
        i("CD_GRAU_ESCOLARIDADE") + " AS cd_grau_escolaridade",
        i("CD_RACA_COR") + " AS cd_raca_cor",
        big(eleit_col) + " AS qt_eleitores_perfil",
        big("QT_ELEITORES_BIOMETRIA") + " AS qt_eleitores_biometria",
        big("QT_ELEITORES_DEFICIENCIA") + " AS qt_eleitores_deficiencia",
        big(ns_col) + " AS qt_eleitores_nome_social",
    ]
    print(f"  carregando perfil eleitorado -> ano {ano} ...")
    con.execute(f"DELETE FROM fact_eleitorado_perfil WHERE ano_eletivo = {ano}")
    con.execute(f"""
        INSERT INTO fact_eleitorado_perfil
        SELECT {', '.join(sel)}
        FROM {read_csv(path)}
    """)


def load_votacao(con, csvs, ano):
    sp = [c for c in csvs if "_SP.csv" in c.name]
    if not sp:
        print("  AVISO: sem arquivo SP para votacao", ano)
        return
    path = str(sp[0])
    hdr = header_of(Path(path))

    base = [
        f"{ano} AS ano_eletivo",
        col_or_null("CD_TIPO_ELEICAO", hdr, i) + " AS cd_tipo_eleicao",
        col_or_null("NM_TIPO_ELEICAO", hdr) + " AS nm_tipo_eleicao",
        col_or_null("CD_ELEICAO", hdr, i) + " AS cd_eleicao",
        col_or_null("DS_ELEICAO", hdr) + " AS nm_eleicao",
        col_or_null("DT_ELEICAO", hdr) + " AS dt_eleicao",
        i("NR_TURNO") + " AS nr_turno",
        "LPAD(CD_MUNICIPIO,5,'0') AS cd_municipio_tse",
        i("NR_ZONA") + " AS nr_zona",
        i("NR_SECAO") + " AS nr_secao",
        i("NR_LOCAL_VOTACAO") + " AS nr_local_votacao",
        col_or_null("NM_LOCAL_VOTACAO", hdr) + " AS nm_local_votacao",
        i("CD_CARGO") + " AS cd_cargo",
        txt("DS_CARGO") + " AS ds_cargo",
        col_or_null("QT_APTOS", hdr, big) + " AS qt_aptos",
        col_or_null("QT_COMPARECIMENTO", hdr, big) + " AS qt_comparecimento",
        col_or_null("QT_ABSTENCOES", hdr, big) + " AS qt_abstencoes",
        col_or_null("QT_VOTOS_NOMINAIS", hdr, big) + " AS qt_votos_nominais",
        col_or_null("QT_VOTOS_BRANCOS", hdr, big) + " AS qt_votos_brancos",
        col_or_null("QT_VOTOS_NULOS", hdr, big) + " AS qt_votos_nulos",
        col_or_null("QT_VOTOS_LEGENDA", hdr, big) + " AS qt_votos_legenda",
        i("NR_VOTAVEL") + " AS nr_votavel",
        txt("NM_VOTAVEL") + " AS nm_votavel",
        col_or_null("SG_PARTIDO", hdr) + " AS sg_partido",
        col_or_null("SQ_CANDIDATO", hdr, big) + " AS sq_candidato",
        big("QT_VOTOS") + " AS qt_votos",
    ]
    print(f"  carregando votacao por secao -> ano {ano} ...")
    con.execute(f"DELETE FROM fact_votacao_secao WHERE ano_eletivo = {ano}")
    con.execute(f"""
        INSERT INTO fact_votacao_secao
        SELECT {', '.join(base)}
        FROM {read_csv(path)}
    """)


def load_presidente(con, csvs, ano):
    """votacao_secao_{ano}_BR.zip: arquivo NACIONAL com cargo Presidente.
       Filtra SG_UF='SP' e ds_cargo='Presidente' (idempotente por cargo/ano)."""
    br = [c for c in csvs if "_BR.csv" in c.name]
    if not br:
        br = csvs
    if not br:
        print("  AVISO: sem arquivo BR para votacao_presidente", ano)
        return
    path = str(br[0])
    hdr = header_of(Path(path))
    base = [
        f"{ano} AS ano_eletivo",
        col_or_null("CD_TIPO_ELEICAO", hdr, i) + " AS cd_tipo_eleicao",
        col_or_null("NM_TIPO_ELEICAO", hdr) + " AS nm_tipo_eleicao",
        col_or_null("CD_ELEICAO", hdr, i) + " AS cd_eleicao",
        col_or_null("DS_ELEICAO", hdr) + " AS nm_eleicao",
        col_or_null("DT_ELEICAO", hdr) + " AS dt_eleicao",
        i("NR_TURNO") + " AS nr_turno",
        "LPAD(CD_MUNICIPIO,5,'0') AS cd_municipio_tse",
        i("NR_ZONA") + " AS nr_zona",
        i("NR_SECAO") + " AS nr_secao",
        i("NR_LOCAL_VOTACAO") + " AS nr_local_votacao",
        col_or_null("NM_LOCAL_VOTACAO", hdr) + " AS nm_local_votacao",
        i("CD_CARGO") + " AS cd_cargo",
        txt("DS_CARGO") + " AS ds_cargo",
        col_or_null("QT_APTOS", hdr, big) + " AS qt_aptos",
        col_or_null("QT_COMPARECIMENTO", hdr, big) + " AS qt_comparecimento",
        col_or_null("QT_ABSTENCOES", hdr, big) + " AS qt_abstencoes",
        col_or_null("QT_VOTOS_NOMINAIS", hdr, big) + " AS qt_votos_nominais",
        col_or_null("QT_VOTOS_BRANCOS", hdr, big) + " AS qt_votos_brancos",
        col_or_null("QT_VOTOS_NULOS", hdr, big) + " AS qt_votos_nulos",
        col_or_null("QT_VOTOS_LEGENDA", hdr, big) + " AS qt_votos_legenda",
        i("NR_VOTAVEL") + " AS nr_votavel",
        txt("NM_VOTAVEL") + " AS nm_votavel",
        col_or_null("SG_PARTIDO", hdr) + " AS sg_partido",
        col_or_null("SQ_CANDIDATO", hdr, big) + " AS sq_candidato",
        big("QT_VOTOS") + " AS qt_votos",
    ]
    print(f"  carregando votacao PRESIDENTE (arquivo BR, filtro SP) -> ano {ano} ...")
    con.execute(f"""DELETE FROM fact_votacao_secao
                     WHERE ano_eletivo = {ano} AND UPPER(ds_cargo) = 'PRESIDENTE'""")
    con.execute(f"""
        INSERT INTO fact_votacao_secao
        SELECT {', '.join(base)}
        FROM {read_csv(path)}
        WHERE SG_UF = 'SP' AND UPPER(DS_CARGO) = 'PRESIDENTE'
    """)


def load_candidatos(con, csvs, ano):
    """consulta_cand (BR) -> dim_candidato, filtrando SP (SG_UF='SP')."""
    sp = [c for c in csvs if "_SP.csv" in c.name]
    if not sp:
        sp = csvs
    if not sp:
        print("  AVISO: sem arquivo candidatos", ano)
        return
    path = str(sp[0])
    hdr = header_of(Path(path))
    uf_col = "SG_UF" if "SG_UF" in hdr else None
    print(f"  carregando candidatos -> ano {ano} ...")

    base = [
        f"{ano} AS ano_eletivo",
        col_or_null("SQ_CANDIDATO", hdr, big) + " AS sq_candidato",
        col_or_null("NR_CANDIDATO", hdr, i) + " AS nr_candidato",
        col_or_null("NM_CANDIDATO", hdr) + " AS nm_candidato",
        col_or_null("NM_URNA_CANDIDATO", hdr) + " AS nm_urna_candidato",
        col_or_null("SG_PARTIDO", hdr) + " AS sg_partido",
        col_or_null("NR_PARTIDO", hdr, i) + " AS nr_partido",
        col_or_null("CD_CARGO", hdr, i) + " AS cd_cargo",
        col_or_null("DS_CARGO", hdr) + " AS ds_cargo",
        col_or_null("CD_SITUACAO_CANDIDATURA", hdr, i) + " AS cd_situacao_candidatura",
        col_or_null("DS_SITUACAO_CANDIDATURA", hdr) + " AS ds_situacao_candidatura",
        col_or_null("CD_SITUACAO_TURNO", hdr, i) + " AS cd_situacao_turno",
        col_or_null("DS_SITUACAO_TURNO", hdr) + " AS ds_situacao_turno",
        col_or_null("SG_UF", hdr) + " AS sg_uf",
        col_or_null("CD_GENERO", hdr, i) + " AS cd_genero",
        col_or_null("DS_GENERO", hdr) + " AS ds_genero",
        col_or_null("CD_GRAU_INSTRUCAO", hdr, i) + " AS cd_grau_instrucao",
        col_or_null("DS_GRAU_INSTRUCAO", hdr) + " AS ds_grau_instrucao",
        col_or_null("CD_ESTADO_CIVIL", hdr, i) + " AS cd_estado_civil",
        col_or_null("DS_ESTADO_CIVIL", hdr) + " AS ds_estado_civil",
        col_or_null("CD_COR_RACA", hdr, i) + " AS cd_cor_raca",
        col_or_null("DS_COR_RACA", hdr) + " AS ds_cor_raca",
        col_or_null("DS_OCUPACAO", hdr) + " AS ds_ocupacao",
        col_or_null("SG_UE", hdr) + " AS sg_ue",
        col_or_null("NM_UE", hdr) + " AS nm_ue",
    ]
    clauses = f"""
        SELECT {', '.join(base)} FROM {read_csv(path)}
    """
    if uf_col:
        clauses = f"SELECT * FROM ({clauses}) WHERE sg_uf = 'SP'"
    con.execute(f"DELETE FROM dim_candidato WHERE ano_eletivo = {ano}")
    con.execute(f"INSERT INTO dim_candidato {clauses}")


def load_partido(con):
    print("dim_partido (distinto de candidatos)...")
    con.execute("DELETE FROM dim_partido")
    con.execute("""
        INSERT OR REPLACE INTO dim_partido (nr_partido, sg_partido)
        SELECT nr_partido, MIN(sg_partido)
        FROM dim_candidato
        WHERE nr_partido IS NOT NULL
        GROUP BY nr_partido
    """)
    # dedup definida da base + classificacao campo politico (camada analitica)
    camada = Path(__file__).resolve().parent.parent / "_sql" / "camada_analitica"
    limpeza = camada / "00_limpeza_dim_candidato.sql"
    campo_sql = camada / "01_classificacao_partidos.sql"
    if limpeza.exists():
        con.execute(limpeza.read_text(encoding="utf-8"))
    if campo_sql.exists():
        con.execute(campo_sql.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all",
                    choices=["all", "municipio", "secao", "perfil", "votacao",
                             "presidente", "candidatos", "campos"])
    ap.add_argument("--extract", action="store_true", help="so extrai, nao carrega")
    args = ap.parse_args()

    ensure_dirs()
    manifest = load_manifest()
    print("Fase 1: extracao + normalizacao latin-1 -> utf-8")
    extracted = extract_all(manifest)

    if args.extract:
        print("Extracao concluida.")
        return

    print("Fase 2: carga DuckDB")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS main")
    schema = Path(__file__).resolve().parent.parent / "_sql" / "schema.sql"
    con.execute(schema.read_text(encoding="utf-8"))

    # ADR-008 (2026-09-26): dim_local_votacao precisa de nr_zona na chave (mesmo fix
    # ja aplicado no banco BR). CREATE TABLE IF NOT EXISTS do schema.sql nao altera
    # tabela ja existente -> migra explicitamente se a coluna ainda nao existe.
    cols = [r[0] for r in con.execute("DESCRIBE dim_local_votacao").fetchall()]
    if "nr_zona" not in cols:
        print("ADR-008: migrando dim_local_votacao (adicionando nr_zona na chave)...")
        con.execute("""
            CREATE OR REPLACE TABLE dim_local_votacao (
                ano_eletivo        INTEGER NOT NULL,
                cd_municipio_tse   VARCHAR(5) NOT NULL,
                nr_zona            INTEGER NOT NULL,
                nr_local_votacao   INTEGER NOT NULL,
                nm_local_votacao   VARCHAR,
                ds_tipo_local      VARCHAR,
                ds_endereco        VARCHAR,
                nm_bairro          VARCHAR,
                nr_cep             VARCHAR,
                nr_latitude        DOUBLE,
                nr_longitude       DOUBLE,
                cd_situ_local      INTEGER,
                ds_situ_local      VARCHAR,
                PRIMARY KEY (ano_eletivo, cd_municipio_tse, nr_zona, nr_local_votacao)
            )
        """)

    if args.only in ("all", "municipio"):
        cod = extracted.get("codigos_geral", [])
        if cod:
            load_municipio(con, str(cod[0]))
        else:
            print("AVISO: codigos nao extraidos")

    if args.only in ("all", "secao"):
        for ano in (2022, 2024, 2026):
            csvs = extracted.get(f"local_votacao_{ano}", [])
            if csvs:
                load_secao_local(con, csvs, ano)

    if args.only in ("all", "perfil"):
        for ano in (2020, 2022, 2024, 2026):
            csvs = extracted.get(f"eleitorado_secao_{ano}", [])
            if csvs:
                load_perfil(con, csvs, ano)

    if args.only in ("all", "presidente"):
        for ano in (2014, 2018, 2022, 2026):
            csvs = extracted.get(f"votacao_presidente_{ano}", [])
            if csvs:
                load_presidente(con, csvs, ano)

    if args.only in ("all", "votacao"):
        for ano in (2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026):
            csvs = extracted.get(f"votacao_secao_{ano}", [])
            if csvs:
                load_votacao(con, csvs, ano)

    if args.only in ("all", "candidatos"):
        for ano in (2012, 2014, 2016, 2018, 2020, 2022, 2024, 2026):
            csvs = extracted.get(f"candidatos_{ano}", [])
            if csvs:
                load_candidatos(con, csvs, ano)
        load_partido(con)

    con.close()
    print(f"\nBanco pronto: {DB_PATH}")

    # resumo
    con = duckdb.connect(str(DB_PATH))
    for t in ("dim_municipio", "dim_secao", "dim_local_votacao", "dim_candidato",
              "dim_partido", "fact_eleitorado_local", "fact_eleitorado_perfil",
              "fact_votacao_secao"):
        try:
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:26s} {n:>12,}")
        except Exception as e:
            print(f"  {t:26s} ERRO: {e}")
    con.close()


if __name__ == "__main__":
    sys.exit(main())