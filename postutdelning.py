import requests
import datetime
from icalendar import Calendar, Event
import time
import os

# --- KONFIGURATION ---
POSTNUMMER = "56632"
API_KEY = "447ae136a7bad7f1849b3489e90edc45"

# --- Globala headers med User-Agent och apikey ---
HEADERS = {
    "apikey": API_KEY,
    "User-Agent": "Mozilla/5.0 (compatible; PostutdelningScript/1.0; +https://dindoman.se)"
}

# --- Funktion för GET med retry vid 429 ---
def get_with_retry(url, params=None, max_attempts=5, wait_sec=30):
    attempts = 0
    while attempts < max_attempts:
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", wait_sec))
                attempts += 1
                print(f"Rate limit reached (429). Retry-After: {retry_after} sekunder. Väntar och försöker igen... (försök {attempts} av {max_attempts})")
                time.sleep(retry_after)
            else:
                print(f"HTTPError: {e} - {response.text}")
                raise
    raise Exception(f"Misslyckades efter {max_attempts} försök p.g.a. rate limit (429).")

# --- Health Check för API ---
def health_check():
    url = "https://api2.postnord.com/rest/location/v1/surcharge/manage/health"
    print("Kör Health Check mot Postnord API...")
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        print("Health Check OK:", response.json())
    else:
        raise Exception(f"Health Check misslyckades med statuskod {response.status_code}: {response.text}")

# --- Hämta info om postnummer (X, Y, S) ---
def get_postalcode_info(postnummer):
    url = "https://api2.postnord.com/rest/masterdata/gim/v2/postalcode"
    params = {
        "ids": f"postalcode:{postnummer}"
    }
    data = get_with_retry(url, params=params)
    if not data or "data" not in data or len(data["data"]) == 0:
        raise Exception("Postnummerdata saknas eller ogiltigt format.")
    return data["data"][0]  # första posten

# --- Hämta sorteringsmönster (X/Y/H) för datumintervallet ---
def get_sort_patterns(from_date, to_date):
    url = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
    params = {
        "fromdate": from_date.strftime("%Y-%m-%d"),
        "todate": to_date.strftime("%Y-%m-%d")
    }
    data = get_with_retry(url, params=params)
    if not data or len(data) == 0:
        raise Exception("Sorteringsdata saknas eller tomt svar.")
    # data är en lista av dicts med "plannedDate" och "patternName"
    return {item["plannedDate"]: item["patternName"] for item in data}

# --- Main funktion ---
def main():
    health_check()  # Kör health check först
    
    idag = datetime.date.today()
    slutdatum = idag + datetime.timedelta(days=90)

    print(f"Hämtar postnummerinfo för {POSTNUMMER}...")
    postalcode_info = get_postalcode_info(POSTNUMMER)
    print("Postnummerinfo:", postalcode_info)

    print(f"Hämtar sorteringsmönster från {idag} till {slutdatum}...")
    sort_patterns = get_sort_patterns(idag, slutdatum)
    print(f"Hämtade {len(sort_patterns)} sorteringsdagar.")

    post_pattern = postalcode_info.get("patternName")
    if not post_pattern:
        raise Exception("Kunde inte hitta postnummerns sorteringsmönster (X/Y/S).")

    print(f"Postnummer {POSTNUMMER} har sorteringsmönster: {post_pattern}")

    # --- Skapa kalender ---
    cal = Calendar()
    cal.add("prodid", "-//Postutdelning//SE")
    cal.add("version", "2.0")

    utdelningsdagar = 0

    for datum_str, pattern in sort_patterns.items():
        # Regeln från dokumentationen:
        # Om dagen är X och postnumrets pattern är X eller S → utdelning
        # Om dagen är Y och postnumrets pattern är Y eller S → utdelning
        # H är helg/helgdag, ingen utdelning
        if pattern == "H":
            continue
        if post_pattern == "S" or post_pattern == pattern:
            dt = datetime.datetime.strptime(datum_str, "%Y-%m-%d").date()
            event = Event()
            event.add("summary", "Postutdelning 📬")
            event.add("dtstart", dt)
            event.add("dtend", dt + datetime.timedelta(days=1))
            event.add("dtstamp", datetime.datetime.now())
            cal.add_component(event)
            utdelningsdagar += 1

    # --- Spara kalenderfil ---
    os.makedirs("docs", exist_ok=True)
    ics_path = "docs/postutdelning.ics"
    with open(ics_path, "wb") as f:
        f.write(cal.to_ical())

    print(f"Kalenderfil skapad med {utdelningsdagar} utdelningsdagar på {ics_path}.")

if __name__ == "__main__":
    main()
