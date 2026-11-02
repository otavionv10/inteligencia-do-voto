#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARQUIVO   : _scripts/load_presidente_candidatos.py
FUNCAO    : Carrega candidatos de PRESIDENTE/VICE-PRESIDENTE (consulta_cand BR)
            em dim_candidato e reconstroi dim_candidato_map / _nr + dim_partido.
            Idempotente (DELETE por ano+cargo antes de INSERT).
USO       :
    python _scripts/load_presidente_candidatos.py
"""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DB_PATH, EXTRACTED_DIR  # noqa: E402
import load  # noqa: E402

ANOS = (2014, 2018, 2022)
CARGOS = ("PRESIDENTE", "VICE-PRESIDENTE")


def main():
    con = duckdb.connect(str(DB_PATH))

    for ano in ANOS:
        path = EXTRACTED_DIR / "candidatos" / str(ano) / f"consulta_cand_{ano}_BR.csv"
        if not path.exists():
            print(f"AVISO: {path} nao existe; pulando {ano}")
            continue
        hdr = load.header_of(path)
        posicao_in = ", ".join(
            f"'{c}'" for c in ("PRESIDENTE", "VICE-PRESIDENTE")
        )
        base = [
            f"{ano} AS ano_eletivo",
            load.col_or_null("SQ_CANDIDATO", hdr, load.big) + " AS sq_candidato",
            load.col_or_null("NR_CANDIDATO", hdr, load.i) + " AS nr_candidato",
            load.col_or_null("NM_CANDIDATO", hdr) + " AS nm_candidato",
            load.col_or_null("NM_URNA_CANDIDATO", hdr) + " AS nm_urna_candidato",
            load.col_or_null("SG_PARTIDO", hdr) + " AS sg_partido",
            load.col_or_null("NR_PARTIDO", hdr, load.i) + " AS nr_partido",
            load.col_or_null("CD_CARGO", hdr, load.i) + " AS cd_cargo",
            load.col_or_null("DS_CARGO", hdr) + " AS ds_cargo",
            load.col_or_null("CD_SITUACAO_CANDIDATURA", hdr, load.i) + " AS cd_situacao_candidatura",
            load.col_or_null("DS_SITUACAO_CANDIDATURA", hdr) + " AS ds_situacao_candidatura",
            load.col_or_null("CD_SITUACAO_TURNO", hdr, load.i) + " AS cd_situacao_turno",
            load.col_or_null("DS_SITUACAO_TURNO", hdr) + " AS ds_situacao_turno",
            "'SP' AS sg_uf",
            load.col_or_null("CD_GENERO", hdr, load.i) + " AS cd_genero",
            load.col_or_null("DS_GENERO", hdr) + " AS ds_genero",
            load.col_or_null("CD_GRAU_INSTRUCAO", hdr, load.i) + " AS cd_grau_instrucao",
            load.col_or_null("DS_GRAU_INSTRUCAO", hdr) + " AS ds_grau_instrucao",
            load.col_or_null("CD_ESTADO_CIVIL", hdr, load.i) + " AS cd_estado_civil",
            load.col_or_null("DS_ESTADO_CIVIL", hdr) + " AS ds_estado_civil",
            load.col_or_null("CD_COR_RACA", hdr, load.i) + " AS cd_cor_raca",
            load.col_or_null("DS_COR_RACA", hdr) + " AS ds_cor_raca",
            load.col_or_null("DS_OCUPACAO", hdr) + " AS ds_ocupacao",
            load.col_or_null("SG_UE", hdr) + " AS sg_ue",
            load.col_or_null("NM_UE", hdr) + " AS nm_ue",
        ]
        print(f"carregando candidatos PRESIDENTE/VICE -> ano {ano} ...")
        con.execute(f"""DELETE FROM dim_candidato
                         WHERE ano_eletivo = {ano}
                           AND UPPER(ds_cargo) IN ({posicao_in})""")
        con.execute(f"""
            INSERT INTO dim_candidato
            SELECT {', '.join(base)}
              FROM {load.read_csv(path)}
             WHERE UPPER(DS_CARGO) IN ({posicao_in})""")
        n = con.execute(
            """SELECT COUNT(*) FROM dim_candidato
               WHERE ano_eletivo = ? AND UPPER(ds_cargo) IN (?, ?)""",
            [ano, "PRESIDENTE", "VICE-PRESIDENTE"]).fetchone()[0]
        print(f"  dim_candidato {ano}: {n} linhas de presidente/vice")

    print("reconstruindo dim_candidato_map / dim_candidato_map_nr ...")
    con.execute("""
      CREATE OR REPLACE TABLE dim_candidato_map AS
      SELECT ano_eletivo, sq_candidato, nr_candidato, nm_candidato, sg_partido,
             nr_partido, nm_partido, campo, nota, cd_cargo,
             UPPER(ds_cargo) AS ds_cargo, sg_uf, sg_ue, nm_ue
        FROM vw_candidato_campo""")
    con.execute("""
      CREATE OR REPLACE TABLE dim_candidato_map_nr AS
      SELECT ano_eletivo, nr_candidato, ds_cargo, grupo,
             MIN(nm_candidato) nm_candidato, MIN(sg_partido) sg_partido,
             MIN(nm_partido) nm_partido, MIN(campo) campo
        FROM (SELECT ano_eletivo, nr_candidato, ds_cargo,
                     CASE WHEN ds_cargo IN ('PREFEITO','VICE-PREFEITO','VEREADOR')
                          THEN CAST(sg_ue AS VARCHAR) ELSE sg_uf END AS grupo,
                     nm_candidato, sg_partido, nm_partido, campo
                FROM dim_candidato_map)
       GROUP BY 1,2,3,4""")

    print("refrescando dim_partido + classificacao de campo ...")
    load.load_partido(con)

    for t, where in (("dim_candidato_map", "UPPER(ds_cargo) LIKE '%PRESIDENTE%'"),
                     ("dim_candidato_map_nr", "UPPER(ds_cargo) LIKE '%PRESIDENTE%'")):
        n = con.execute(f"SELECT COUNT(*) FROM {t} WHERE {where}").fetchone()[0]
        print(f"  {t}: {n} linhas de presidente")

    con.close()
    print("OK: candidatos de presidente carregados e mapas reconstruidos.")


if __name__ == "__main__":
    sys.exit(main())