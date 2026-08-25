#!/usr/bin/env python3
"""
SkyFlow — runner das transformações (bronze -> silver -> gold).

Executa os SQLs de sql/silver.sql e sql/gold.sql no DuckDB. Os SQLs
ficam em arquivos próprios (legíveis, versionados); este script apenas
substitui os caminhos e os executa.

Uso:
  python src/run_transform.py            # roda silver e depois gold
  python src/run_transform.py silver     # só a silver
  python src/run_transform.py gold       # só a gold
"""

import os
import sys
import glob
import logging

import duckdb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(PROJECT_ROOT, "sql")
BRONZE_GLOB = os.path.join(PROJECT_ROOT, "data", "bronze", "**", "*.parquet")
SILVER_DIR = os.path.join(PROJECT_ROOT, "data", "silver")
SILVER_OUT = os.path.join(SILVER_DIR, "aircraft_states.parquet")
SILVER_GLOB = os.path.join(SILVER_DIR, "*.parquet")
GOLD_DIR = os.path.join(PROJECT_ROOT, "data", "gold")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("skyflow.transform")


def read_sql(name):
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as f:
        return f.read()


def run_silver(con):
    if not glob.glob(BRONZE_GLOB, recursive=True):
        log.error("Bronze vazia — rode a coleta antes de transformar.")
        sys.exit(1)
    os.makedirs(SILVER_DIR, exist_ok=True)
    sql = read_sql("silver.sql").replace(
        "{BRONZE_GLOB}", BRONZE_GLOB.replace("\\", "/")
    ).replace(
        "{SILVER_OUT}", SILVER_OUT.replace("\\", "/")
    )
    con.execute(sql)
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{SILVER_GLOB.replace(chr(92), '/')}')"
    ).fetchone()[0]
    log.info("Silver gerada: %d linhas em %s", n, SILVER_OUT)


def run_gold(con):
    if not glob.glob(SILVER_GLOB):
        log.error("Silver vazia — rode a etapa silver antes da gold.")
        sys.exit(1)
    os.makedirs(GOLD_DIR, exist_ok=True)
    sql = read_sql("gold.sql").replace(
        "{SILVER_GLOB}", SILVER_GLOB.replace("\\", "/")
    ).replace(
        "{GOLD_DIR}", GOLD_DIR.replace("\\", "/")
    )
    con.execute(sql)
    marts = glob.glob(os.path.join(GOLD_DIR, "*.parquet"))
    log.info("Gold gerada: %d marts (%s)",
             len(marts), ", ".join(os.path.basename(m) for m in marts))


def main():
    etapa = sys.argv[1] if len(sys.argv) > 1 else "all"
    con = duckdb.connect()
    if etapa in ("silver", "all"):
        run_silver(con)
    if etapa in ("gold", "all"):
        run_gold(con)
    if etapa not in ("silver", "gold", "all"):
        log.error("Etapa inválida: %s (use silver, gold ou nada para ambas)", etapa)
        sys.exit(1)
    con.close()


if __name__ == "__main__":
    main()
