import requests
import datetime
from icalendar import Calendar, Event
import time
import os
import json

# --- KONFIGURATION ---
POSTNUMMER = "56632"
API_KEY = "447ae136a7bad7f1849b3489e90edc45"
CACHE_DIR = "cache"
LOG_FILE = "cache/api_call_count.log"
POSTALCODE_CACHE_FILE = os.path.join(CACHE_DIR, f"postalcode_{POSTNUMMER}.json")
SORTPATTERN_CACHE_FILE = os.path.join(CACHE_DIR, "sortpatterns.json")

# --- Globala headers ---
HEADERS = {
    "apikey": API_KEY,
    "User-Agent": "Mozilla/5.0 (compatible; PostutdelningScript/1.0; +https://dindoman.se)"
}

# --- Hjälpfunktion för att logga antal anrop ---
def log_api_call():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    count = 0
    if os.path.isfile(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            content = f.read()
            if content.isdigit():
                count = int(content)
    count += 1
    with open(LOG_FILE, "w") as f:
        f.write(str(count))
    print(f"API-anrop totalt under detta körning: {count}")

# --- Hjälpfunktion: GET med retry och hantering av 429 ---
def get_with_retry(url, params=None, max_attempts=5, wait_sec=30):
    attempts = 0
    while attempts < max_attempts:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else wait_sec
            attempts += 1
            print(f"Rate limit reached (429). Retry-After: {wait} sekunder. Väntar och försöker igen... (försök {attempts} av {max_attempts})")
            time.sleep(wait)
        else:
            response.raise_for_status()
            log_api_call()
            return response.json()
    raise Exception(f"Misslyckades efter {max_attempts} försök p.g.a. rate limit (429).")

# --- Läs/skriv cache ---
def load_cache(filename, max_age_sec):
    if not os.path.isfile(filename):
        return None
    mod_time = os.path.getmtime(filename)
    age = time.time() - mod_time
    if age > max_age_sec:
        print(f"Cachen {filename} är gammal ({age:.0f} sek), hämtar nytt.")
        return None
    with open(filename, "r", encoding="utf-8") as f:
        print(f"Läser data från cache {filename}.")
        return json.load(f)

def save_cache(filename, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"Sparar data till cache {filename}.")

# --- Hämta postnummerinfo med caching ---
def get_postalcode_info(postnummer):
    cache = load_cache(POSTALCODE_CACHE_FILE, max_age_sec=24*3600)  # 1 dag
    if cache:
        return cache
    print(f"Hämtar postnummerinfo för {postnummer} från API...")
    url = "https://api2.postnord.com/rest/masterdata/gim/v2/postalcode"
    params = {"ids": f"postalcode:{postnummer}"}
    data = get_with_retry(url, params=params)
    if not data or "data" not in data or len(data["data"]) == 0:
        raise Exception("Postnummerdata saknas eller ogiltigt format.")
    save_cache(POSTALCODE_CACHE_FILE, data["data"][0])
    return data["data"][0]

# --- Hämta sorteringsmönster med caching ---
def get_sort_patterns(from_date, to_date):
    cache = load_cache(SORTPATTERN_CACHE_FILE, max_age_sec=24*3600)  # 1 dag
    if cache:
        return cache
    print(f"Hämtar sorteringsmönster från API...")
    url = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
    params = {
        "fromdate": from_date.strftime("%Y-%m-%d"),
        "todate": to_date.strftime("%Y-%m-%d")
    }
    data = get_with_retry(url, params=params)
    if not data or len(data) == 0:
        raise Exception("Sorteringsdata saknas eller tomt svar.")
    patterns = {item["plannedDate"]: item["patternName"] for item in data}
    save_cache(SORTPATTERN_CACHE_FILE, patterns)
    return patterns

# --- Skapa kalenderfil ---
def create_calendar(utdelningsdagar):
    cal = Calendar()
    cal.add("prodid", "-//Postutdelning//SE")
    cal.add("version", "2.0")

    for dt in utdelningsdagar:
        event = Event()
        event.add("summary", "Postutdelning 📬")
        event.add("dtstart", dt)
        event.add("dtend", dt + datetime.timedelta(days=1))
        event.add("dtstamp", datetime.datetime.now())
        cal.add_component(event)

    os.makedirs("docs", exist_ok=True)
    ics_path = "docs/postutdelning.ics"
    with open(ics_path, "wb") as f:
        f.write(cal.to_ical())
    print(f"Kalenderfil skapad med {len(utdelningsdagar)} utdelningsdagar på {ics_path}.")

# --- Main ---
def main():
    idag = datetime.date.today()
    slutdatum = idag + datetime.timedelta(days=90)

    postalcode_info = get_postalcode_info(POSTNUMMER)
    print("Postnummerinfo:", postalcode_info)

    sort_patterns = get_sort_patterns(idag, slutdatum)
    print(f"Hämtade {len(sort_patterns)} sorteringsdagar.")

    post_pattern = postalcode_info.get("patternName")
    if not post_pattern:
        raise Exception("Kunde inte hitta postnummerns sorteringsmönster (X/Y/S).")
    print(f"Postnummer {POSTNUMMER} har sorteringsmönster: {post_pattern}")

    utdelningsdagar = []
    for datum_str, pattern in sort_patterns.items():
        if pattern == "H":  # helg/helgdag, ingen utdelning
            continue
        if post_pattern == "S" or post_pattern == pattern:
            dt = datetime.datetime.strptime(datum_str, "%Y-%m-%d").date()
            utdelningsdagar.append(dt)

    create_calendar(utdelningsdagar)

if __name__ == "__main__":
    main()
