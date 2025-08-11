import requests
import json
import os
import time
from datetime import datetime, timedelta
from ics import Calendar, Event

# ---- KONFIG ----
API_KEY = "447ae136a7bad7f1849b3489e90edc45"
POSTNUMMER = "56632"
DAGAR_FRAMÅT = 90
FILNAMN = "postutdelning.ics"

CACHE_DIR = "cache"
POSTALCODE_CACHE_FILE = os.path.join(CACHE_DIR, "cache_postalcode.json")
SORTPATTERNS_CACHE_FILE = os.path.join(CACHE_DIR, "cache_sortpatterns.json")

CACHE_MAX_AGE_SECONDS = 24 * 3600  # 24 timmar cache-livslängd

HEADERS = {
    "apikey": API_KEY,
    "User-Agent": "Mozilla/5.0 (PostutdelningScript)"
}

def read_cache(file_path):
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        # Kontrollera ålder på cache
        cache_time = cached.get("cache_time", 0)
        if time.time() - cache_time > CACHE_MAX_AGE_SECONDS:
            print(f"Cachefil {file_path} är gammal, ignorerar cache.")
            return None
        return cached.get("data")
    except Exception as e:
        print(f"Fel vid läsning av cachefil {file_path}: {e}")
        return None

def write_cache(file_path, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_data = {
        "cache_time": time.time(),
        "data": data
    }
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"Fel vid sparande av cachefil {file_path}: {e}")

def get_with_retry(url, params=None, max_attempts=5, wait_sec=30):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", wait_sec))
                attempts += 1
                print(f"Rate limit reached (429). Väntar {retry_after} sekunder och försöker igen... (försök {attempts} av {max_attempts})")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Fel vid anrop: {e}")
            raise
    raise Exception(f"Misslyckades efter {max_attempts} försök p.g.a. rate limit (429).")

def get_postalcode_pattern(postnummer):
    # Försök läsa från cache
    cached = read_cache(POSTALCODE_CACHE_FILE)
    if cached:
        print(f"Använder cache för postnummerinfo ({postnummer})")
        return cached.get("patternName")

    url = "https://api2.postnord.com/rest/masterdata/gim/v2/postalcode"
    params = {"ids": f"postalcode:{postnummer}"}
    data = get_with_retry(url, params=params)

    if not data or "data" not in data or len(data["data"]) == 0:
        raise Exception(f"Ingen data för postnummer {postnummer}")

    pattern = data["data"][0].get("patternName")
    if not pattern:
        raise Exception(f"Postnummer {postnummer} saknar sorteringsmönster (X/Y/S)")

    print(f"Hämtade postnummerinfo från API: {postnummer} → mönster: {pattern}")
    write_cache(POSTALCODE_CACHE_FILE, data["data"][0])
    return pattern

def get_sort_patterns(from_date, to_date):
    # Försök läsa från cache (kolla att cachedatum stämmer med dagens datum och intervallet)
    cached = read_cache(SORTPATTERNS_CACHE_FILE)
    if cached:
        cache_from = cached[0].get("plannedDate") if len(cached) > 0 else None
        cache_to = cached[-1].get("plannedDate") if len(cached) > 0 else None
        wanted_from = from_date.strftime("%Y-%m-%d")
        wanted_to = to_date.strftime("%Y-%m-%d")
        if cache_from <= wanted_from and cache_to >= wanted_to:
            print(f"Använder cache för sorteringsmönster från {wanted_from} till {wanted_to}")
            return cached

    url = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
    params = {
        "fromdate": from_date.strftime("%Y-%m-%d"),
        "todate": to_date.strftime("%Y-%m-%d"),
    }
    data = get_with_retry(url, params=params)

    if not isinstance(data, list):
        raise Exception("Oväntat svar från sortpatterns API")

    print(f"Hämtade sorteringsmönster från API: {len(data)} dagar.")
    write_cache(SORTPATTERNS_CACHE_FILE, data)
    return data

def skapa_ics(utdelningsdagar):
    cal = Calendar()
    for entry in utdelningsdagar:
        datum_str = entry.get("plannedDate") if isinstance(entry, dict) else entry
        e = Event()
        e.name = "Postutdelning 📬"
        e.begin = datum_str
        e.make_all_day()
        cal.events.add(e)

    with open(FILNAMN, "w", encoding="utf-8") as f:
        f.writelines(cal)
    print(f"ICS-fil skapad: {FILNAMN}")

def main():
    idag = datetime.today()
    slutdatum = idag + timedelta(days=DAGAR_FRAMÅT)

    post_pattern = get_postalcode_pattern(POSTNUMMER)
    sort_patterns = get_sort_patterns(idag, slutdatum)

    utdelningsdagar = []
    for entry in sort_patterns:
        datum_str = entry.get("plannedDate")
        dag_pattern = entry.get("patternName")

        if dag_pattern == "H":
            continue
        if post_pattern == "S" or post_pattern == dag_pattern:
            utdelningsdagar.append(datum_str)

    print(f"Totalt {len(utdelningsdagar)} utdelningsdagar hittades för postnummer {POSTNUMMER}.")

    if utdelningsdagar:
        skapa_ics(utdelningsdagar)
    else:
        print("Inga utdelningsdagar att skapa kalender för.")

if __name__ == "__main__":
    import time
    main()
