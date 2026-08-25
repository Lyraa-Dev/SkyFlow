import os
import duckdb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD_DIR = os.path.join(PROJECT_ROOT, "data", "gold").replace("\\", "/")


def show(con, titulo, query):
    print("\n" + "=" * 60)
    print(titulo)
    print("=" * 60)
    try:
        df = con.execute(query).fetchdf()
        print(df.to_string(index=False))
    except Exception as e:
        print(f"(não foi possível ler: {e})")


def main():
    con = duckdb.connect()

    show(con, "TRÁFEGO POR HORA (últimas 10 janelas)", f"""
        SELECT ingest_date, hour, total_observacoes, aeronaves_distintas,
               em_voo, em_solo, altitude_media_m, velocidade_media_kmh
        FROM read_parquet('{GOLD_DIR}/trafego_por_hora.parquet')
        ORDER BY ingest_date DESC, hour DESC
        LIMIT 10
    """)

    show(con, "DENSIDADE POR REGIÃO (acumulado)", f"""
        SELECT regiao_aprox,
               SUM(observacoes) AS observacoes,
               SUM(aeronaves_distintas) AS soma_aeronaves
        FROM read_parquet('{GOLD_DIR}/densidade_por_regiao.parquet')
        GROUP BY regiao_aprox
        ORDER BY observacoes DESC
    """)

    show(con, "RANKING DE PAÍSES (top 10 acumulado)", f"""
        SELECT origin_country,
               SUM(observacoes) AS observacoes,
               SUM(aeronaves_distintas) AS soma_aeronaves
        FROM read_parquet('{GOLD_DIR}/ranking_paises.parquet')
        GROUP BY origin_country
        ORDER BY observacoes DESC
        LIMIT 10
    """)

    con.close()


if __name__ == "__main__":
    main()