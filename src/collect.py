import os
import sys
import json
import time
import logging
from datetime import datetime, timezone

import requests
import pandas as pd
import duckdb

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/"
    "opensky-network/protocol/openid-connect/token"
)
STATES_URL = "https://opensky-network.org/api/states/all"
BRAZIL_BBOX = {"lamin": -34.0, "lomin": -74.0, "lamax": 6.0, "lomax": -34.0}

STATE_FIELDS = [
    "icao24", "callsign", "origin_country", "time_position",
    "last_contact", "longitude", "latitude", "baro_altitude",
    "on_ground", "velocity", "true_track", "vertical_rate",
    "sensors", "geo_altitude", "squawk", "spi", "position_source",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRONZE_DIR = os.path.join(PROJECT_ROOT, "data", "bronze")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("skyflow.collect")

def load_credentials():
    cid = os.getenv("OPENSKY_CLIENT_ID")
    csecret = os.getenv("OPENSKY_CLIENT_SECRET")
    if cid and csecret:
        return cid, csecret

    path = os.path.join(PROJECT_ROOT, "credentials.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        cid = data.get("clientId") or data.get("client_id")
        csecret = data.get("clientSecret") or data.get("client_secret")
        if cid and csecret:
            return cid, csecret

    log.error("Credenciais não encontradas (env ou credentials.json).")
    sys.exit(1)


def get_token(client_id, client_secret):
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if resp.status_code != 200:
        log.error("Falha ao obter token (%s): %s", resp.status_code, resp.text[:200])
        sys.exit(1)
    log.info("Token obtido com sucesso.")
    return resp.json()["access_token"]


def fetch_states(token, bbox, max_retries=4):
    headers = {"Authorization": f"Bearer {token}"}
    delay = 2
    for attempt in range(1, max_retries + 1):
        resp = requests.get(STATES_URL, headers=headers, params=bbox, timeout=45)

        if resp.status_code == 200:
            remaining = resp.headers.get("X-Rate-Limit-Remaining")
            if remaining is not None:
                log.info("Cota restante hoje: %s", remaining)
            return resp.json()

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", delay))
            log.warning("Rate limit (429). Aguardando %ss (tentativa %d/%d).",
                        retry_after, attempt, max_retries)
            time.sleep(retry_after)
            delay *= 2
            continue

        log.error("Erro na coleta (%s): %s", resp.status_code, resp.text[:200])
        sys.exit(1)

    log.error("Esgotadas as tentativas por rate limit.")
    sys.exit(1)

def to_dataframe(payload):
    """Converte o payload cru em DataFrame, preservando tudo (bronze = cru)."""
    states = payload.get("states") or []
    api_time = payload.get("time")

    rows = []
    for s in states:
        rec = dict(zip(STATE_FIELDS, s))
        cs = rec.get("callsign")
        rec["callsign"] = cs.strip() if isinstance(cs, str) else None
        # 'sensors' é lista/None — não cabe em coluna Parquet simples; descartamos.
        rec.pop("sensors", None)
        rec["api_time"] = api_time
        rows.append(rec)

    df = pd.DataFrame(rows)
    # timestamp de ingestão (UTC) — quando NÓS coletamos, não quando o avião reportou
    now = datetime.now(timezone.utc)
    df["ingestion_ts"] = now.isoformat()
    df["ingest_date"] = now.strftime("%Y-%m-%d")
    df["hour"] = now.strftime("%H")
    return df, now


def write_bronze(df, now):
    """Grava Parquet particionado por ingest_date/hour, com nome único por coleta."""
    os.makedirs(BRONZE_DIR, exist_ok=True)
    # nome único: evita sobrescrever se rodar 2x na mesma hora (ex.: rerun manual)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    con = duckdb.connect()
    con.register("df", df)
    con.execute(
        f"""
        COPY (SELECT * FROM df)
        TO '{BRONZE_DIR}'
        (FORMAT PARQUET,
         PARTITION_BY (ingest_date, hour),
         FILENAME_PATTERN 'states_{stamp}_{{i}}',
         OVERWRITE_OR_IGNORE)
        """
    )
    con.close()

def main():
    log.info("Iniciando coleta SkyFlow.")
    cid, csecret = load_credentials()
    token = get_token(cid, csecret)
    payload = fetch_states(token, BRAZIL_BBOX)

    df, now = to_dataframe(payload)
    n = len(df)
    if n == 0:
        # não é erro: pode haver momentos sem aeronaves. Loga e sai limpo.
        log.warning("Nenhuma aeronave retornada. Nada a gravar.")
        return

    write_bronze(df, now)
    airborne = int((~df["on_ground"].fillna(True)).sum())
    log.info("Coleta OK: %d aeronaves (%d em voo) gravadas na bronze "
             "(ingest_date=%s hour=%s).",
             n, airborne, df["ingest_date"].iloc[0], df["hour"].iloc[0])


if __name__ == "__main__":
    main()
