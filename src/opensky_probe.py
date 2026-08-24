import os
import sys
import json
import time
from datetime import datetime, timezone

import requests

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/"
    "opensky-network/protocol/openid-connect/token"
)
STATES_URL = "https://opensky-network.org/api/states/all"

BRAZIL_BBOX = {"lamin": -34.0, "lomin": -74.0, "lamax": 6.0, "lomax": -34.0}

# Ordem dos campos do state vector, conforme a API REST da OpenSky.
STATE_FIELDS = [
    "icao24", "callsign", "origin_country", "time_position",
    "last_contact", "longitude", "latitude", "baro_altitude",
    "on_ground", "velocity", "true_track", "vertical_rate",
    "sensors", "geo_altitude", "squawk", "spi", "position_source",
]


def load_credentials():
    cid = os.getenv("OPENSKY_CLIENT_ID")
    csecret = os.getenv("OPENSKY_CLIENT_SECRET")
    if cid and csecret:
        return cid, csecret

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "credentials.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        cid = data.get("clientId") or data.get("client_id")
        csecret = data.get("clientSecret") or data.get("client_secret")
        if cid and csecret:
            return cid, csecret

    sys.exit(
        "ERRO: credenciais não encontradas.\n"
        "Exporte OPENSKY_CLIENT_ID e OPENSKY_CLIENT_SECRET, "
        "ou coloque credentials.json ao lado do script."
    )


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
        sys.exit(f"ERRO ao obter token ({resp.status_code}): {resp.text[:300]}")
    tok = resp.json()
    print(f"[auth] token obtido, expira em {tok.get('expires_in')}s")
    return tok["access_token"]


def fetch_states(token, bbox, max_retries=4):
    headers = {"Authorization": f"Bearer {token}"}
    delay = 2
    for attempt in range(1, max_retries + 1):
        resp = requests.get(STATES_URL, headers=headers, params=bbox, timeout=45)

        if resp.status_code == 200:
            remaining = resp.headers.get("X-Rate-Limit-Remaining")
            if remaining is not None:
                print(f"[cota] chamadas restantes hoje: {remaining}")
            return resp.json()

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", delay))
            print(f"[429] rate limit; aguardando {retry_after}s "
                  f"(tentativa {attempt}/{max_retries})")
            time.sleep(retry_after)
            delay *= 2
            continue

        sys.exit(f"ERRO na coleta ({resp.status_code}): {resp.text[:300]}")

    sys.exit("ERRO: esgotadas as tentativas por rate limit.")


def to_record(state):
    rec = dict(zip(STATE_FIELDS, state))
    cs = rec.get("callsign")
    rec["callsign"] = cs.strip() if isinstance(cs, str) else None
    return rec


def summarize(payload):
    ts = payload.get("time")
    states = payload.get("states") or []
    when = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "?"

    print("\n" + "=" * 60)
    print("SNAPSHOT DO TRÁFEGO AÉREO — BRASIL")
    print("=" * 60)
    print(f"Timestamp da API : {when}")
    print(f"Aeronaves no box : {len(states)}")

    records = [to_record(s) for s in states]
    with_pos = [r for r in records if r["latitude"] is not None]
    airborne = [r for r in with_pos if not r["on_ground"]]

    print(f"Com posição      : {len(with_pos)}")
    print(f"Em voo (airborne): {len(airborne)}")

    # top 5 distribuição por país de origem 
    from collections import Counter
    origins = Counter(r["origin_country"] for r in with_pos)
    print("\nTop países de origem:")
    for country, n in origins.most_common(5):
        print(f"  {country:<25} {n}")

    print("\nAmostra (5 aeronaves em voo):")
    print(f"  {'icao24':<8} {'callsign':<9} {'país':<14} "
          f"{'alt(m)':>7} {'vel(km/h)':>9}")
    for r in airborne[:5]:
        vel = r['velocity']
        vel_kmh = round(vel * 3.6, 1) if vel is not None else None
        alt = r['baro_altitude']
        print(f"  {r['icao24']:<8} {str(r['callsign'] or '')[:8]:<9} "
              f"{str(r['origin_country'])[:13]:<14} "
              f"{('' if alt is None else round(alt)):>7} "
              f"{('' if vel_kmh is None else vel_kmh):>9}")

    # salva o bruto para inspeção posterior, ao lado do script
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "opensky_snapshot.json")
    with open(out, "w") as f:
        json.dump(payload, f)
    print(f"\n[ok] snapshot bruto salvo em {out}")

    # registro bruto completo, para vermos o formato exato do evento
    if records:
        print("\nExemplo de UM registro tratado (vira 1 evento no Kinesis):")
        print(json.dumps(records[0], indent=2, ensure_ascii=False))


def main():
    cid, csecret = load_credentials()
    token = get_token(cid, csecret)
    payload = fetch_states(token, BRAZIL_BBOX)
    summarize(payload)


if __name__ == "__main__":
    main()