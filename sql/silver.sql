COPY (
    WITH bronze AS (
        SELECT *
        FROM read_parquet('{BRONZE_GLOB}', hive_partitioning => true)
    ),

    -- 1. mantém só o que tem posição válida
    com_posicao AS (
        SELECT *
        FROM bronze
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
    ),

    -- 2 + 3. normaliza campos e corrige on_ground nulo
    normalizado AS (
        SELECT
            icao24,
            NULLIF(callsign, '')                       AS callsign,
            origin_country,
            time_position,
            longitude,
            latitude,
            baro_altitude                              AS altitude_m,
            -- conversão de velocidade para km/h (fonte vem em m/s)
            ROUND(velocity * 3.6, 1)                   AS velocidade_kmh,
            true_track                                 AS rumo_graus,
            vertical_rate                              AS taxa_vertical_ms,
            -- correção do on_ground: se nulo, infere por vel~0 e alt<=0
            COALESCE(
                on_ground,
                (COALESCE(velocity, 0) < 1
                 AND COALESCE(baro_altitude, 0) <= 0)
            )                                          AS on_ground,
            ingestion_ts,
            ingest_date,
            hour,
            -- 5. macrorregião aproximada por bounding box de lat/lon
            CASE
                WHEN latitude BETWEEN -5.5 AND 6.0  AND longitude BETWEEN -74.0 AND -46.0 THEN 'Norte'
                WHEN latitude BETWEEN -18.0 AND -1.0 AND longitude BETWEEN -48.0 AND -34.0 THEN 'Nordeste'
                WHEN latitude BETWEEN -25.0 AND -14.0 AND longitude BETWEEN -61.0 AND -50.0 THEN 'Centro-Oeste'
                WHEN latitude BETWEEN -25.5 AND -14.0 AND longitude BETWEEN -50.0 AND -39.0 THEN 'Sudeste'
                WHEN latitude BETWEEN -34.0 AND -22.0 AND longitude BETWEEN -58.0 AND -48.0 THEN 'Sul'
                ELSE 'Fora/Indefinido'
            END                                        AS regiao_aprox
        FROM com_posicao
    ),

    -- 4. dedup: fica com o registro mais recente por (icao24, time_position)
    dedup AS (
        SELECT *
        FROM normalizado
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY icao24, time_position
            ORDER BY ingestion_ts DESC
        ) = 1
    )

    SELECT * FROM dedup
)
TO '{SILVER_OUT}' (FORMAT PARQUET, OVERWRITE_OR_IGNORE);
-- NOTA — região por bounding box (aproximação consciente):
-- A OpenSky fornece lat/lon e o país de REGISTRO da aeronave, não a
-- UF sobrevoada. Derivar a UF real exigiria join geoespacial (ponto
-- em polígono), que foge do escopo. As caixas
-- acima se sobrepõem nas fronteiras e ignoram o recorte irregular
-- dos estados — servem para uma visão macro, não para precisão
-- cartográfica. Em produção: usar as malhas geográficas do IBGE
-- (GeoJSON) com ST_Contains da extensão espacial do DuckDB.

