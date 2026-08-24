import os
import duckdb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRONZE_GLOB = os.path.join(PROJECT_ROOT, "data", "bronze", "**", "*.parquet")


def main():
    con = duckdb.connect()
    src = f"read_parquet('{BRONZE_GLOB}', hive_partitioning=true)"

    total = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    if total == 0:
        print("Bronze vazia — nenhum Parquet encontrado ainda.")
        return

    print("=" * 55)
    print("RESUMO DA CAMADA BRONZE")
    print("=" * 55)
    print(f"Total de registros : {total}")

    parts = con.execute(f"""
        SELECT ingest_date, hour, count(*) AS registros
        FROM {src}
        GROUP BY ingest_date, hour
        ORDER BY ingest_date, hour
    """).fetchdf()
    print(f"\nParticoes (coletas por hora):\n{parts.to_string(index=False)}")

    origins = con.execute(f"""
        SELECT origin_country, count(*) AS aeronaves
        FROM {src}
        GROUP BY origin_country
        ORDER BY aeronaves DESC
        LIMIT 5
    """).fetchdf()
    print(f"\nTop 5 paises de origem (acumulado):\n{origins.to_string(index=False)}")

    sample = con.execute(f"""
        SELECT icao24, callsign, origin_country,
               round(baro_altitude) AS alt_m,
               round(velocity * 3.6, 1) AS vel_kmh
        FROM {src}
        WHERE on_ground = false AND callsign IS NOT NULL
        LIMIT 5
    """).fetchdf()
    print(f"\nAmostra (5 aeronaves em voo):\n{sample.to_string(index=False)}")

    con.close()


if __name__ == "__main__":
    main()