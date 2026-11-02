"""
=============================================================================
ARQUIVO   : _scripts/load_brasil.py
FUNCAO    : ETL dos dados TSE -> DuckDB NACIONAL (todas as UFs)
            Cria banco separado data/db/brasil.duckdb (~30 GB).
DEPENDE   : duckdb>=1.5, common.py, schema.sql, camada_analitica
USO       :
   python _scripts/load_brasil.py               # tudo (municipio, secao, perfil,
                                                #   votacao UF, presidente BR, candidatos)
   python _scripts/load_brasil.py --only votacao   # so votacao por UF
   python _scripts/load_brasil.py --only presidente
   python _scripts/load_brasil.py --only candidatos
DIFERENCAS p/ load.py (SP):
   - DB_PATH = data/db/brasil.duckdb (banco separado)
   - Todas as UFs (nenhum filtro SG_UF='SP')
   - Candidatos: usa consulta_cand_*_BRASIL.csv (consolidado nacional)
   - Presidente: arquivo _BR.csv inteiro (todas UFs)
   - dim_local_votacao CARREGADA com nr_zona na chave (fix ADR-008):
     chave (ano_eletivo, cd_municipio, nr_zona, nr_local_votacao)
CRIADO    : 2026-09-22 (spin-off do load.py para nivel BRASIL)
=============================================================================
"""
import argparse
import sys
from pathlib import Path

from common import (RAW_DIR, EXTRACTED_DIR, IBGE_DIR,
                    ensure_dirs, load_manifest)
import duckdb

DB_PATH = EXTRACTED_DIR.parent / "db" / "brasil.duckdb"

Q = lambda s: f'"{s}"'


def iq(s):  # inteiro
    return f"CAST(NULLIF(TRIM({s}),'') AS INTEGER)"


def bq(s):  # bigint
    return f"CAST(NULLIF(TRIM({s}),'') AS BIGINT)"


def dq(s):  # double
    return f"CAST(NULLIF(TRIM(REPLACE(REPLACE({s},',','.'),'\"','')),'') AS DOUBLE)"


def tq(s):
    return s


def read_csv(path: str):
    # aceita substring com '*' (glob) ou lista sendo convertida a seguir
    return (f"read_csv_auto('{path}', header=true, delim=';', "
            f"all_varchar=true, sample_size=-1, nullstr='', dateformat='%d/%m/%Y')")


def read_csvs(csvs):
    """Lê vários CSVs unindo por nome de coluna (colunas ausentes -> NULL).
       Necessário p/ anos em que UFs têm schemas diferentes (perfil 2022 DF)."""
    glob_str = "','".join(str(c) for c in csvs)
    return (f"read_csv_auto(['{glob_str}'], header=true, delim=';', "
            f"all_varchar=true, union_by_name=true, sample_size=-1, "
            f"nullstr='', dateformat='%d/%m/%Y')")


def header_of(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        line = f.readline()
    return [c.strip().strip('"') for c in line.rstrip("\r\n").split(";")]


def exists(col: str, hdr: list[str]) -> bool:
    return col in hdr


def co_null(col: str, hdr: list[str], cast=tq):
    return cast(col) if exists(col, hdr) else "NULL"


# ---------------------------------------------------------------------------
# CARGA NACIONAL
# ---------------------------------------------------------------------------

def load_municipio(con, csv_path):
    print("dim_municipio (mapa TSE<->IBGE, todas UFs)...")
    con.execute(f"""
        INSERT OR REPLACE INTO dim_municipio
        SELECT LPAD(CD_MUNICIPIO_TSE,5,'0'), NM_MUNICIPIO_TSE,
               LPAD(CD_MUNICIPIO_IBGE,7,'0'), SG_UF, NM_UF
        FROM {read_csv(str(csv_path))}
    """)


def load_secao_local(con, csvs, ano):
    """dim_secao + dim_local_votacao + fact_eleitorado_local (todas UFs).
       dim_local_votacao: chave com nr_zona (fix ADR-008 aplicado no banco BR)."""
    if not csvs:
        print("  AVISO: sem local_votacao", ano)
        return
    # concatena os CSVs distintos do ano (todas as UFs)
    r = read_csvs(csvs)
    print(f"  carregando secao/local/eleitorado -> ano {ano} ({len(csvs)} arquivos) ...")
    con.execute(f"DELETE FROM dim_secao WHERE ano_eletivo = {ano}")
    con.execute(f"DELETE FROM dim_local_votacao WHERE ano_eletivo = {ano}")
    con.execute(f"DELETE FROM fact_eleitorado_local WHERE ano_eletivo = {ano}")

    con.execute(f"""
        INSERT INTO dim_local_votacao
        SELECT {ano}, LPAD(CD_MUNICIPIO,5,'0'), {iq('NR_ZONA')},
               {iq('NR_LOCAL_VOTACAO')},
               MAX(NM_LOCAL_VOTACAO), MAX(DS_TIPO_LOCAL), MAX(DS_ENDERECO),
               MAX(NM_BAIRRO), MAX(NR_CEP),
               MAX({dq('NR_LATITUDE')}), MAX({dq('NR_LONGITUDE')}),
               MAX({iq('CD_SITU_LOCAL_VOTACAO')}), MAX(DS_SITU_LOCAL_VOTACAO)
        FROM {r}
        GROUP BY CD_MUNICIPIO, NR_ZONA, NR_LOCAL_VOTACAO
    """)

    con.execute(f"""
        INSERT INTO dim_secao
        SELECT {ano}, LPAD(CD_MUNICIPIO,5,'0'), {iq('NR_ZONA')}, {iq('NR_SECAO')},
               MAX({iq('CD_TIPO_SECAO_AGREGADA')}), MAX(DS_TIPO_SECAO_AGREGADA),
               MAX({iq('NR_SECAO_PRINCIPAL')}),
               MAX({iq('CD_SITU_SECAO')}), MAX(DS_SITU_SECAO),
               MAX({iq('CD_SITU_SECAO_ACESSIBILIDADE')}), MAX(DS_SITU_SECAO_ACESSIBILIDADE)
        FROM {r}
        GROUP BY CD_MUNICIPIO, NR_ZONA, NR_SECAO
    """)

    con.execute(f"""
        INSERT INTO fact_eleitorado_local
        SELECT {ano}, {iq('NR_TURNO')}, LPAD(CD_MUNICIPIO,5,'0'),
               {iq('NR_ZONA')}, {iq('NR_SECAO')}, {iq('NR_LOCAL_VOTACAO')},
               {bq('QT_ELEITOR_SECAO')}, {bq('QT_ELEITOR_ELEICAO_FEDERAL')},
               {bq('QT_ELEITOR_ELEICAO_ESTADUAL')}, {bq('QT_ELEITOR_ELEICAO_MUNICIPAL')}
        FROM {r}
    """)


def load_perfil(con, csvs, ano):
    if not csvs:
        print("  AVISO: sem perfil", ano)
        return
    r = read_csvs(csvs)
    hdr = header_of(csvs[0])
    ano_col = "AA_ELEICAO" if "AA_ELEICAO" in hdr else "ANO_ELEICAO"
    eleit_col = "QT_ELEITORES" if "QT_ELEITORES" in hdr and "QT_ELEITORES_PERFIL" not in hdr else "QT_ELEITORES_PERFIL"
    ns_col = "QT_ELEITORES_NOME_SOCIAL" if "QT_ELEITORES_NOME_SOCIAL" in hdr else "QT_ELEITORES_INC_NM_SOCIAL"

    sel = [
        f"{ano} AS ano_eletivo",
        "NULL AS cd_eleicao",
        "LPAD(CD_MUNICIPIO,5,'0') AS cd_municipio_tse",
        iq("NR_ZONA") + " AS nr_zona",
        iq("NR_SECAO") + " AS nr_secao",
        iq("NR_LOCAL_VOTACAO") + " AS nr_local_votacao",
        tq("DS_GENERO") + " AS ds_genero",
        tq("DS_ESTADO_CIVIL") + " AS ds_estado_civil",
        tq("DS_GRAU_ESCOLARIDADE") + " AS ds_grau_escolaridade",
        tq("DS_FAIXA_ETARIA") + " AS ds_faixa_etaria",
        tq("DS_RACA_COR") + " AS ds_cor_raca",
        iq("CD_IDENTIDADE_GENERO") + " AS cd_identidade_genero",
        tq("DS_IDENTIDADE_GENERO") + " AS ds_identidade_genero",
        iq("CD_QUILOMBOLA") + " AS cd_quilombola",
        tq("DS_QUILOMBOLA") + " AS ds_quilombola",
        iq("CD_INTERPRETE_LIBRAS") + " AS cd_interprete_libras",
        tq("DS_INTERPRETE_LIBRAS") + " AS ds_interprete_libras",
        co_null("TP_OBRIGATORIEDADE_VOTO", hdr) + " AS tp_obrigatoriedade_voto",
        iq("CD_GENERO") + " AS cd_genero",
        iq("CD_ESTADO_CIVIL") + " AS cd_estado_civil",
        iq("CD_FAIXA_ETARIA") + " AS cd_faixa_etaria",
        iq("CD_GRAU_ESCOLARIDADE") + " AS cd_grau_escolaridade",
        iq("CD_RACA_COR") + " AS cd_raca_cor",
        bq(eleit_col) + " AS qt_eleitores_perfil",
        bq("QT_ELEITORES_BIOMETRIA") + " AS qt_eleitores_biometria",
        bq("QT_ELEITORES_DEFICIENCIA") + " AS qt_eleitores_deficiencia",
        bq(ns_col) + " AS qt_eleitores_nome_social",
    ]
    print(f"  carregando perfil eleitorado -> ano {ano} ({len(csvs)} arquivos) ...")
    con.execute(f"DELETE FROM fact_eleitorado_perfil WHERE ano_eletivo = {ano}")
    con.execute(f"""
        INSERT INTO fact_eleitorado_perfil
        SELECT {', '.join(sel)}
        FROM {r}
    """)


def load_votacao(con, csvs, ano):
    """Votação por seção dos arquivos por UF (todas UFs, cargos estaduais/federais)."""
    if not csvs:
        print("  AVISO: sem votacao", ano)
        return
    r = read_csvs(csvs)
    hdr = header_of(csvs[0])

    base = [
        f"{ano} AS ano_eletivo",
        co_null("CD_TIPO_ELEICAO", hdr, iq) + " AS cd_tipo_eleicao",
        co_null("NM_TIPO_ELEICAO", hdr) + " AS nm_tipo_eleicao",
        co_null("CD_ELEICAO", hdr, iq) + " AS cd_eleicao",
        co_null("DS_ELEICAO", hdr) + " AS nm_eleicao",
        co_null("DT_ELEICAO", hdr) + " AS dt_eleicao",
        iq("NR_TURNO") + " AS nr_turno",
        "LPAD(CD_MUNICIPIO,5,'0') AS cd_municipio_tse",
        iq("NR_ZONA") + " AS nr_zona",
        iq("NR_SECAO") + " AS nr_secao",
        iq("NR_LOCAL_VOTACAO") + " AS nr_local_votacao",
        co_null("NM_LOCAL_VOTACAO", hdr) + " AS nm_local_votacao",
        iq("CD_CARGO") + " AS cd_cargo",
        tq("DS_CARGO") + " AS ds_cargo",
        co_null("QT_APTOS", hdr, bq) + " AS qt_aptos",
        co_null("QT_COMPARECIMENTO", hdr, bq) + " AS qt_comparecimento",
        co_null("QT_ABSTENCOES", hdr, bq) + " AS qt_abstencoes",
        co_null("QT_VOTOS_NOMINAIS", hdr, bq) + " AS qt_votos_nominais",
        co_null("QT_VOTOS_BRANCOS", hdr, bq) + " AS qt_votos_brancos",
        co_null("QT_VOTOS_NULOS", hdr, bq) + " AS qt_votos_nulos",
        co_null("QT_VOTOS_LEGENDA", hdr, bq) + " AS qt_votos_legenda",
        iq("NR_VOTAVEL") + " AS nr_votavel",
        tq("NM_VOTAVEL") + " AS nm_votavel",
        co_null("SG_PARTIDO", hdr) + " AS sg_partido",
        co_null("SQ_CANDIDATO", hdr, bq) + " AS sq_candidato",
        bq("QT_VOTOS") + " AS qt_votos",
    ]
    print(f"  carregando votacao por secao -> ano {ano} ({len(csvs)} arquivos) ...")
    con.execute(f"DELETE FROM fact_votacao_secao WHERE ano_eletivo = {ano}")
    con.execute(f"""
        INSERT INTO fact_votacao_secao
        SELECT {', '.join(base)}
        FROM {r}
    """)


def load_presidente(con, csv_path, ano):
    """Arquivo nacional _BR.csv: TODAS as UFs, cargo Presidente."""
    if not csv_path:
        print("  AVISO: sem arquivo BR presidente", ano)
        return
    r = read_csv(str(csv_path))
    hdr = header_of(csv_path)
    base = [
        f"{ano} AS ano_eletivo",
        co_null("CD_TIPO_ELEICAO", hdr, iq) + " AS cd_tipo_eleicao",
        co_null("NM_TIPO_ELEICAO", hdr) + " AS nm_tipo_eleicao",
        co_null("CD_ELEICAO", hdr, iq) + " AS cd_eleicao",
        co_null("DS_ELEICAO", hdr) + " AS nm_eleicao",
        co_null("DT_ELEICAO", hdr) + " AS dt_eleicao",
        iq("NR_TURNO") + " AS nr_turno",
        "LPAD(CD_MUNICIPIO,5,'0') AS cd_municipio_tse",
        iq("NR_ZONA") + " AS nr_zona",
        iq("NR_SECAO") + " AS nr_secao",
        iq("NR_LOCAL_VOTACAO") + " AS nr_local_votacao",
        co_null("NM_LOCAL_VOTACAO", hdr) + " AS nm_local_votacao",
        iq("CD_CARGO") + " AS cd_cargo",
        tq("DS_CARGO") + " AS ds_cargo",
        co_null("QT_APTOS", hdr, bq) + " AS qt_aptos",
        co_null("QT_COMPARECIMENTO", hdr, bq) + " AS qt_comparecimento",
        co_null("QT_ABSTENCOES", hdr, bq) + " AS qt_abstencoes",
        co_null("QT_VOTOS_NOMINAIS", hdr, bq) + " AS qt_votos_nominais",
        co_null("QT_VOTOS_BRANCOS", hdr, bq) + " AS qt_votos_brancos",
        co_null("QT_VOTOS_NULOS", hdr, bq) + " AS qt_votos_nulos",
        co_null("QT_VOTOS_LEGENDA", hdr, bq) + " AS qt_votos_legenda",
        iq("NR_VOTAVEL") + " AS nr_votavel",
        tq("NM_VOTAVEL") + " AS nm_votavel",
        co_null("SG_PARTIDO", hdr) + " AS sg_partido",
        co_null("SQ_CANDIDATO", hdr, bq) + " AS sq_candidato",
        bq("QT_VOTOS") + " AS qt_votos",
    ]
    print(f"  carregando votacao PRESIDENTE (arquivo BR, TODAS UFs) -> ano {ano} ...")
    con.execute(f"""DELETE FROM fact_votacao_secao
                     WHERE ano_eletivo = {ano} AND UPPER(ds_cargo) = 'PRESIDENTE'""")
    con.execute(f"""
        INSERT INTO fact_votacao_secao
        SELECT {', '.join(base)}
        FROM {r}
        WHERE UPPER(DS_CARGO) = 'PRESIDENTE'
    """)


def load_candidatos(con, csv_path, ano):
    """consulta_cand_*_BRASIL.csv: consolidado nacional, TODAS UFs + BR (presidente)."""
    if not csv_path:
        print("  AVISO: sem candidatos consolidado", ano)
        return
    hdr = header_of(csv_path)
    r = read_csv(str(csv_path))

    base = [
        f"{ano} AS ano_eletivo",
        co_null("SQ_CANDIDATO", hdr, bq) + " AS sq_candidato",
        co_null("NR_CANDIDATO", hdr, iq) + " AS nr_candidato",
        co_null("NM_CANDIDATO", hdr) + " AS nm_candidato",
        co_null("NM_URNA_CANDIDATO", hdr) + " AS nm_urna_candidato",
        co_null("SG_PARTIDO", hdr) + " AS sg_partido",
        co_null("NR_PARTIDO", hdr, iq) + " AS nr_partido",
        co_null("CD_CARGO", hdr, iq) + " AS cd_cargo",
        co_null("DS_CARGO", hdr) + " AS ds_cargo",
        co_null("CD_SITUACAO_CANDIDATURA", hdr, iq) + " AS cd_situacao_candidatura",
        co_null("DS_SITUACAO_CANDIDATURA", hdr) + " AS ds_situacao_candidatura",
        co_null("CD_SITUACAO_TURNO", hdr, iq) + " AS cd_situacao_turno",
        co_null("DS_SITUACAO_TURNO", hdr) + " AS ds_situacao_turno",
        co_null("SG_UF", hdr) + " AS sg_uf",
        co_null("CD_GENERO", hdr, iq) + " AS cd_genero",
        co_null("DS_GENERO", hdr) + " AS ds_genero",
        co_null("CD_GRAU_INSTRUCAO", hdr, iq) + " AS cd_grau_instrucao",
        co_null("DS_GRAU_INSTRUCAO", hdr) + " AS ds_grau_instrucao",
        co_null("CD_ESTADO_CIVIL", hdr, iq) + " AS cd_estado_civil",
        co_null("DS_ESTADO_CIVIL", hdr) + " AS ds_estado_civil",
        co_null("CD_COR_RACA", hdr, iq) + " AS cd_cor_raca",
        co_null("DS_COR_RACA", hdr) + " AS ds_cor_raca",
        co_null("DS_OCUPACAO", hdr) + " AS ds_ocupacao",
        co_null("SG_UE", hdr) + " AS sg_ue",
        co_null("NM_UE", hdr) + " AS nm_ue",
    ]
    print(f"  carregando candidatos (consolidado BRASIL) -> ano {ano} ...")
    con.execute(f"DELETE FROM dim_candidato WHERE ano_eletivo = {ano}")
    con.execute(f"INSERT INTO dim_candidato SELECT {', '.join(base)} FROM {r}")


def load_partido(con):
    print("dim_partido (distinto de candidatos BR)...")
    con.execute("DELETE FROM dim_partido")
    con.execute("""
        INSERT OR REPLACE INTO dim_partido (nr_partido, sg_partido)
        SELECT nr_partido, MIN(sg_partido)
        FROM dim_candidato
        WHERE nr_partido IS NOT NULL
        GROUP BY nr_partido
    """)
    camada = Path(__file__).resolve().parent.parent / "_sql" / "camada_analitica"
    for f in ("00_limpeza_dim_candidato.sql", "01_classificacao_partidos.sql"):
        p = camada / f
        if p.exists():
            con.execute(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all",
                    choices=["all", "municipio", "secao", "perfil", "votacao",
                             "presidente", "candidatos"])
    ap.add_argument("--recreate", action="store_true",
                    help="dropa e recria o banco brasil.duckdb do zero")
    args = ap.parse_args()

    ensure_dirs()
    manifest = load_manifest()

    def files(tipo_ano):
        """Retorna lista de Paths dos CSVs extraídos do tipo_ano."""
        out = []
        for it in manifest:
            key = f"{it['tipo']}_{it['ano'] or 'geral'}"
            if key != tipo_ano:
                continue
            zp = RAW_DIR / it["local"]
            od = EXTRACTED_DIR / it["tipo"] / str(it["ano"] or "geral")
            if zp.exists():
                pass
            # arquivos reais extraídos (podem existir com nomes do zip e do unpack)
            if od.exists():
                for csv in sorted(od.glob("*.csv")):
                    if csv.stat().st_size > 0:
                        out.append(csv)
        # dedup mantendo ordem
        seen, uniq = set(), []
        for p in out:
            if str(p) not in seen:
                seen.add(str(p))
                uniq.append(p)
        return uniq

    def pick_exact(dirpath, fragment):
        hits = [p for p in dirpath.glob("*.csv") if fragment in p.name]
        return hits[0] if hits else None

    if args.recreate and DB_PATH.exists():
        print(f"Recriando banco: apagando {DB_PATH}")
        DB_PATH.unlink()

    print("Fase 1: verificando CSVs extraidos")
    # municípios
    cod_dir = EXTRACTED_DIR / "codigos" / "geral"
    codigo_csv = pick_exact(cod_dir, "municipio_tse_ibge")
    # local_votacao por ano
    loc = {ano: files(f"local_votacao_{ano}") for ano in (2022, 2024, 2026)}
    # perfil por ano
    per = {ano: files(f"eleitorado_secao_{ano}") for ano in (2020, 2022, 2024, 2026)}
    # votacao por UF por ano (exclui _BR que é presidente)
    vot = {}
    for ano in (2012, 2014, 2016, 2018, 2020, 2022, 2024):
        vot[ano] = files(f"votacao_secao_{ano}")
    # presidente (arquivos _BR.csv)
    pres = {}
    for ano in (2014, 2018, 2022):
        d = EXTRACTED_DIR / "votacao_presidente" / str(ano)
        pres[ano] = pick_exact(d, f"_{ano}_BR.csv") or (pick_exact(d, "_BR.csv") if d.exists() else None)
    # candidatos (consolidado BRASIL)
    cand = {}
    for ano in (2012, 2014, 2016, 2018, 2020, 2022, 2024):
        d = EXTRACTED_DIR / "candidatos" / str(ano)
        cand[ano] = pick_exact(d, f"consulta_cand_{ano}_BRASIL.csv")

    n_vo = sum(len(v) for v in vot.values())
    print(f"  local_votacao: { {k: len(v) for k, v in loc.items()} }")
    print(f"  perfil:        { {k: len(v) for k, v in per.items()} }")
    print(f"  votacao UF:    { {k: len(v) for k, v in vot.items()} } (total {n_vo})")
    print(f"  presidente BR: { {k: (v.name if v else None) for k, v in pres.items()} }")
    print(f"  candidatos:    { {k: (v.name if v else None) for k, v in cand.items()} }")
    print(f"  municipios:    {codigo_csv.name if codigo_csv else 'NAO ENCONTRADO!'}")

    print("Fase 2: carga DuckDB (Brasil)")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    schema = Path(__file__).resolve().parent.parent / "_sql" / "schema.sql"
    con.execute(schema.read_text(encoding="utf-8"))
    # ADR-008 fix: dim_local_votacao passa a ter nr_zona na chave.
    # Só recria quando a tabela não existe ou está vazia (não apagar carga já feita).
    n_lv = con.execute("SELECT COUNT(*) FROM dim_local_votacao").fetchone()[0]
    if n_lv == 0:
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

    if args.only in ("all", "municipio") and codigo_csv:
        load_municipio(con, codigo_csv)

    if args.only in ("all", "secao"):
        for ano in (2022, 2024, 2026):
            if loc[ano]:
                load_secao_local(con, loc[ano], ano)

    if args.only in ("all", "perfil"):
        for ano in (2020, 2022, 2024, 2026):
            if per[ano]:
                load_perfil(con, per[ano], ano)

    if args.only in ("all", "presidente"):
        for ano in (2014, 2018, 2022):
            if pres[ano]:
                load_presidente(con, pres[ano], ano)

    if args.only in ("all", "votacao"):
        for ano in (2012, 2014, 2016, 2018, 2020, 2022, 2024):
            if vot[ano]:
                load_votacao(con, vot[ano], ano)

    if args.only in ("all", "candidatos"):
        for ano in (2012, 2014, 2016, 2018, 2020, 2022, 2024):
            if cand[ano]:
                load_candidatos(con, cand[ano], ano)
        load_partido(con)

    con.close()
    print(f"\nBanco pronto: {DB_PATH}")

    con = duckdb.connect(str(DB_PATH))
    for t in ("dim_municipio", "dim_secao", "dim_local_votacao", "dim_candidato",
              "dim_partido", "fact_eleitorado_local", "fact_eleitorado_perfil",
              "fact_votacao_secao"):
        try:
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t:26s} {n:>14,}")
        except Exception as e:
            print(f"  {t:26s} ERRO: {e}")
    con.close()


if __name__ == "__main__":
    sys.exit(main())