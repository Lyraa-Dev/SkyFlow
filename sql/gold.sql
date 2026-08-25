-- FATO 1 — Tráfego por hora e região

COPY (
    SELECT
        ingest_date,
        hour,
        regiao_aprox,
        COUNT(*)                                   AS total_observacoes,
        COUNT(DISTINCT icao24)                     AS aeronaves_distintas,
        COUNT(*) FILTER (WHERE NOT on_ground)      AS em_voo,
        COUNT(*) FILTER (WHERE on_ground)          AS em_solo,
        ROUND(AVG(altitude_m) FILTER (WHERE NOT on_ground), 0) AS altitude_media_m,
        ROUND(AVG(velocidade_kmh) FILTER (WHERE NOT on_ground), 1) AS velocidade_media_kmh
    FROM read_parquet('{SILVER_GLOB}', hive_partitioning => true)
    GROUP BY ingest_date, hour, regiao_aprox
    ORDER BY ingest_date, hour, regiao_aprox
)
TO '{GOLD_DIR}/trafego_por_hora.parquet' (FORMAT PARQUET, OVERWRITE_OR_IGNORE);

-- FATO 2 — Densidade por região
COPY (
    SELECT
        regiao_aprox,
        ingest_date,
        hour,
        COUNT(*)                                   AS observacoes,
        COUNT(DISTINCT icao24)                     AS aeronaves_distintas,
        ROUND(AVG(altitude_m) FILTER (WHERE NOT on_ground), 0) AS altitude_media_m
    FROM read_parquet('{SILVER_GLOB}', hive_partitioning => true)
    GROUP BY regiao_aprox, ingest_date, hour
    ORDER BY ingest_date, hour, observacoes DESC
)
TO '{GOLD_DIR}/densidade_por_regiao.parquet' (FORMAT PARQUET, OVERWRITE_OR_IGNORE);

-- FATO 3 — Ranking de países de origem (agora com região)
COPY (
    SELECT
        origin_country,
        ingest_date,
        regiao_aprox,
        COUNT(*)                                   AS observacoes,
        COUNT(DISTINCT icao24)                     AS aeronaves_distintas
    FROM read_parquet('{SILVER_GLOB}', hive_partitioning => true)
    GROUP BY origin_country, ingest_date, regiao_aprox
    ORDER BY ingest_date, aeronaves_distintas DESC
)
TO '{GOLD_DIR}/ranking_paises.parquet' (FORMAT PARQUET, OVERWRITE_OR_IGNORE);

-- DIMENSÃO — Data
COPY (
    SELECT DISTINCT
        ingest_date,
        CAST(ingest_date AS DATE)                  AS data,
        EXTRACT(dow FROM CAST(ingest_date AS DATE)) AS dia_semana_num
    FROM read_parquet('{SILVER_GLOB}', hive_partitioning => true)
    ORDER BY ingest_date
)
TO '{GOLD_DIR}/dim_data.parquet' (FORMAT PARQUET, OVERWRITE_OR_IGNORE);

-- DIMENSÃO — Região
COPY (
    SELECT DISTINCT regiao_aprox
    FROM read_parquet('{SILVER_GLOB}', hive_partitioning => true)
    ORDER BY regiao_aprox
)
TO '{GOLD_DIR}/dim_regiao.parquet' (FORMAT PARQUET, OVERWRITE_OR_IGNORE);