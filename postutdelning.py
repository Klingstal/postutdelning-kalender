#!/usr/bin/env python3
import os
import json
import time
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

import requests
from icalendar import Calendar, Event

# ========= KONFIG =========
API_KEY = "447ae136a7bad7f1849b3489e90edc45"
POSTNUMMER = "56632"
DAGAR_FRAMAT = 90  # hur långt fram vi planerar
ICS_FIL = "docs/postutdelning.ics"

# Caching (24h)
CACHE_DIR = "cache"
POSTALCODE_CACHE = os.path.join(CACHE_DIR, f"postalcode_{POSTNUMMER}.json")
SORTPATTERNS_CACHE = os.path.join(CACHE_DIR, "sortpatterns.json")
CACHE_TTL_SEK = 24 * 3600

# HTTP
USER_AGENT = "PostutdelningKalender/1.0 (+github.com/Klingstal/postutdelning-kalender)"
MAX_TRIES = 5
DEFAULT_WAIT = 30  # sekunder
# ==========================


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def ensure_dirs() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(ICS_FIL) or ".", exist_ok=True)


def is_cache_fresh(path: str, ttl_seconds: int = CACHE_TTL_SEK) -> bool:
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        ts = payload.get("_cached_at", 0)
        return (time.time() - ts) < ttl_seconds
    except Exception:
        return False


def read_cache(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("data")


def write_cache(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"_cached_at": time.time(), "data": data}, f)


def http_get_json(url: str, params: Dict[str, str]) -> dict | list:
    """
    GET med apikey i query, 429-hantering och enkel backoff.
    """
    tries = 0
    while True:
        tries += 1
        try:
            # Lägg alltid in apikey i params (utan att skriva över ev. befintlig)
            final_params = dict(params) if params else {}
            final_params.setdefault("apikey", API_KEY)

            logging.info(f"Anropar: {url}  params={final_params}")
            r = requests.get(url, params=final_params, headers={"User-Agent": USER_AGENT}, timeout=30)

            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", DEFAULT_WAIT))
                logging.warning(f"Rate limit (429). Retry-After: {wait}s. Försök {tries}/{MAX_TRIES}")
                if tries >= MAX_TRIES:
                    r.raise_for_status()
                time.sleep(wait)
                continue

            r.raise_for_status()
            # Försök JSON först, fall tillbaka till text
            try:
                return r.json()
            except ValueError:
                return {"raw": r.text}

        except requests.RequestException as e:
            logging.error(f"HTTP-fel: {e}")
            if tries >= MAX_TRIES:
                raise
            time.sleep(DEFAULT_WAIT)


def bygg_urls(idag: date, slut: date) -> Tuple[str, str]:
    """
    Returnerar de två exakta URL:erna (inkl. query) som vi kommer att kalla.
    Praktiskt för att kunna klistra in i webbläsaren och testa.
    """
    base_sort = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
    base_post = "https://api2.postnord.com/rest/masterdata/gim/v2/postalcode"

    # OBS: apikey är i query enligt PostNord-dokumentationen
    sort_url = (
        f"{base_sort}"
        f"?apikey={API_KEY}"
        f"&fromdate={idag.strftime('%Y-%m-%d')}"
        f"&todate={slut.strftime('%Y-%m-%d')}"
    )
    post_url = (
        f"{base_post}"
        f"?apikey={API_KEY}"
        f"&ids=postalcode:{POSTNUMMER}"
    )
    return sort_url, post_url


def hamta_postnummer_monster() -> str:
    """
    Hämtar om postnummer är X, Y eller S.
    Cache: 24h
    """
    if is_cache_fresh(POSTALCODE_CACHE):
        data = read_cache(POSTALCODE_CACHE)
        pattern = (data or {}).get("patternName")
        if pattern:
            logging.info(f"Postnummer {POSTNUMMER} (cache): pattern={pattern}")
            return pattern

    url = "https://api2.postnord.com/rest/masterdata/gim/v2/postalcode"
    params = {"ids": f"postalcode:{POSTNUMMER}"}
    data = http_get_json(url, params)

    # Förväntat format: {"data": [ { "patternName": "X" | "Y" | "S", ... } ]}
    if not isinstance(data, dict) or "data" not in data or not data["data"]:
        raise RuntimeError(f"Oväntat svar från postalcode: {data}")

    entry = data["data"][0]
    pattern = entry.get("patternName")
    if not pattern:
        raise RuntimeError("Saknar patternName i postalcode-svar")

    write_cache(POSTALCODE_CACHE, entry)
    logging.info(f"Postnummer {POSTNUMMER} (API): pattern={pattern}")
    return pattern


def hamta_sortpatterns(idag: date, slut: date) -> List[Dict[str, str]]:
    """
    Hämtar lista av {plannedDate, patternName} för datumintervallet.
    Cache: 24h. Vi sparar med från- och t.o.m.-datum i cachen.
    """
    # Om cache finns och täcker intervallet – använd
    if is_cache_fresh(SORTPATTERNS_CACHE):
        cached = read_cache(SORTPATTERNS_CACHE) or {}
        c_from = cached.get("_from")
        c_to = cached.get("_to")
        c_list = cached.get("list", [])
        want_from = idag.strftime("%Y-%m-%d")
        want_to = slut.strftime("%Y-%m-%d")

        if c_from and c_to and c_list:
            if c_from <= want_from <= c_to and c_from <= want_to <= c_to:
                logging.info(f"Använder cache för sortpatterns {c_from}..{c_to} (täcker {want_from}..{want_to})")
                return c_list

    # Annars hämta nytt – hämtar exakt intervallet vi behöver
    url = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
    params = {
        "fromdate": idag.strftime("%Y-%m-%d"),
        "todate": slut.strftime("%Y-%m-%d"),
    }
    data = http_get_json(url, params)

    # Förväntat: en lista [{"plannedDate":"YYYY-MM-DD", "patternName":"X|Y|H", ...}, ...]
    if not isinstance(data, list):
        raise RuntimeError(f"Oväntat svar från sortpatterns: {data}")

    # Sortera på datum för säkerhets skull
    data_sorted = sorted(
        data,
        key=lambda d: d.get("plannedDate", "")
    )

    cache_payload = {
        "_from": idag.strftime("%Y-%m-%d"),
        "_to": slut.strftime("%Y-%m-%d"),
        "list": data_sorted
    }
    write_cache(SORTPATTERNS_CACHE, cache_payload)
    logging.info(f"Hämtade {len(data_sorted)} sortpattern-dagar från API")
    return data_sorted


def berakna_utdelningsdagar(post_pattern: str, dagar: List[Dict[str, str]]) -> List[str]:
    """
    Regler:
      - H = helg/helgdag → ingen utdelning
      - S-postnummer = utdelning alla dagar som inte är H
      - X-postnummer → utdelning bara på X-dagar
      - Y-postnummer → utdelning bara på Y-dagar
    Returnerar lista YYYY-MM-DD som har utdelning.
    """
    out = []
    for entry in dagar:
        datum = entry.get("plannedDate")
        pattern = entry.get("patternName")
        if not datum or not pattern:
            continue
        if pattern == "H":
            continue
        if post_pattern == "S" or post_pattern == pattern:
            out.append(datum)
    return out


def skriv_ics(datum_lista: List[str], fil: str) -> None:
    cal = Calendar()
    cal.add("prodid", "-//Postutdelning//SE")
    cal.add("version", "2.0")

    for d in datum_lista:
        # dtstart och dtend (nästa dag) för heldags-event
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        event = Event()
        event.add("summary", "Postutdelning 📬")
        event.add("dtstart", dt)
        event.add("dtend", dt + timedelta(days=1))
        event.add("dtstamp", datetime.now())
        cal.add_component(event)

    with open(fil, "wb") as f:
        f.write(cal.to_ical())
    logging.info(f"Skrev {len(datum_lista)} dagar till {fil}")


def main():
    setup_logging()
    ensure_dirs()

    idag = date.today()
    slut = idag + timedelta(days=DAGAR_FRAMAT)

    # Visa de exakta URL:erna som kommer att anropas (bra för manuell testning i webbläsaren)
    sort_url, post_url = bygg_urls(idag, slut)
    print("\n--- TESTA I WEBBLÄSAREN (kopiera/klistra) ---")
    print("Sortpatterns-url:")
    print(sort_url)
    print("\nPostalcode-url:")
    print(post_url)
    print("--------------------------------------------\n")

    # Hämta (med cache)
    post_pattern = hamta_postnummer_monster()
    sort_days = hamta_sortpatterns(idag, slut)

    utdelningsdagar = berakna_utdelningsdagar(post_pattern, sort_days)
    logging.info(f"Postnummer {POSTNUMMER} ({post_pattern}) → {len(utdelningsdagar)} utdelningsdagar inom {DAGAR_FRAMAT} dagar")

    if not utdelningsdagar:
        logging.warning("Inga utdelningsdagar hittades – skriver ändå tom ICS.")
    skriv_ics(utdelningsdagar, ICS_FIL)


if __name__ == "__main__":
    main()
