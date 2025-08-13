import requests
import json
import time
from datetime import datetime, timedelta
from ics import Calendar, Event
import os

# ======= KONFIGURATION =======
API_KEY = "447ae136a7bad7f1849b3489e90edc45"
POSTNUMMER = "56632"
CACHE_FILE = "cache.json"
ICS_FIL = "postutdelning.ics"
ANTAL_DAGAR = 30
MAX_RETRIES = 5
WAIT_TIME = 30  # sekunder vid rate limit
# ============================


def get_with_retry(url, params=None):
    """API-anrop med retry vid rate limit (429)."""
    for attempt in range(MAX_RETRIES):
        r = requests.get(url, params=params)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print(f"Rate limit (429). Väntar {WAIT_TIME} sekunder... (försök {attempt+1}/{MAX_RETRIES})")
            time.sleep(WAIT_TIME)
        else:
            r.raise_for_status()
    raise Exception("Misslyckades efter max försök p.g.a. rate limit.")


def hamta_sortpattern_id(postnummer):
    """Steg 1: Hämta sort pattern ID från PostNord postalcode-API."""
    url = f"https://api2.postnord.com/rest/shipment/v1/postalcode/{postnummer}"
    params = {
        "apikey": API_KEY,
        "countryCode": "SE",
        "context": "servicepoint"
    }
    data = get_with_retry(url, params=params)
    
    try:
        sortpattern_id = data["postalCodeInformationResponse"]["postalCodeInformation"][0]["deliverySchedule"]["sortPatternId"]
        return sortpattern_id
    except KeyError:
        raise Exception("Kunde inte hitta sortPatternId i svaret från postalcode-API:t.")


def hamta_utdelningsdagar(sortpattern_id):
    """Steg 2: Hämta utdelningsdagar från PostNord daterange-API."""
    url = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
    start_date = datetime.today().strftime("%Y-%m-%d")
    end_date = (datetime.today() + timedelta(days=ANTAL_DAGAR)).strftime("%Y-%m-%d")
    
    params = {
        "apikey": API_KEY,
        "sortPatternId": sortpattern_id,
        "startDate": start_date,
        "endDate": end_date
    }
    data = get_with_retry(url, params=params)
    
    dagar = []
    try:
        for item in data["deliveryDates"]:
            dagar.append(item["date"])
    except KeyError:
        raise Exception("Kunde inte läsa deliveryDates från daterange-API:t.")
    
    return dagar


def load_cache():
    """Läs cache från fil."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(data):
    """Spara cache till fil."""
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


def skapa_ics(dagar):
    """Skapa ICS-kalenderfil."""
    cal = Calendar()
    for dag in dagar:
        event = Event()
        event.name = "Postutdelning"
        event.begin = dag
        cal.events.add(event)
    with open(ICS_FIL, "w") as f:
        f.writelines(cal)
    print(f"ICS-fil skapad: {ICS_FIL}")


def main():
    cache = load_cache()
    idag = datetime.today().strftime("%Y-%m-%d")
    
    # Använd cache om den är färsk
    if "datum" in cache and cache["datum"] == idag:
        print("Använder cache...")
        dagar = cache["dagar"]
    else:
        print("Hämtar ny data från PostNord...")
        sortpattern_id = hamta_sortpattern_id(POSTNUMMER)
        dagar = hamta_utdelningsdagar(sortpattern_id)
        save_cache({"datum": idag, "dagar": dagar})
    
    print("Utdelningsdagar:", dagar)
    skapa_ics(dagar)


if __name__ == "__main__":
    main()
