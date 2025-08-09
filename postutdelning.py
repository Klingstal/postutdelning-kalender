import requests
import time
import json
import os
from datetime import datetime, timedelta

# === KONFIGURATION ===
API_KEY = "DIN_API_KEY_HÄR"
CACHE_TTL = 3600  # sekunder (1 timme)
CACHE_FILE = "cache.json"
LOG_FILE = "app.log"

# === HJÄLPFUNKTIONER ===
def log(message):
    """Logga med tidsstämpel till fil."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")

def load_cache():
    """Läs cache från fil."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """Spara cache till fil."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)

def health_check():
    """Kontrollera API-hälsa."""
    url = f"https://host.example.com/rest/location/v1/surcharge/manage/health?apikey={API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        log(f"Health check OK: {data}")
        return True
    except requests.exceptions.RequestException as e:
        log(f"Health check FAILED: {e}")
        return False

def get_postal_surcharge(postal_code):
    """Hämta surcharge-data för ett postnummer med cache."""
    cache = load_cache()
    now = datetime.now()

    # Kolla om cache finns och är färsk
    if postal_code in cache:
        entry = cache[postal_code]
        if now - datetime.fromisoformat(entry["timestamp"]) < timedelta(seconds=CACHE_TTL):
            log(f"Använder cache för {postal_code}")
            return entry["data"]

    # Annars hämta från API
    url = f"https://host.example.com/rest/location/v1/surcharge/manage/{postal_code}?apikey={API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        log(f"Hämtat data för {postal_code} från API")
        cache[postal_code] = {"timestamp": now.isoformat(), "data": data}
        save_cache(cache)
        return data
    except requests.exceptions.RequestException as e:
        log(f"Fel vid hämtning för {postal_code}: {e}")
        return None

# === MAIN ===
def main():
    if not health_check():
        log("API ej tillgängligt – avslutar.")
        return

    test_postcode = "12345"
    data = get_postal_surcharge(test_postcode)
    if data:
        log(f"Resultat för {test_postcode}: {data}")
    else:
        log(f"Ingen data för {test_postcode}")

if __name__ == "__main__":
    main()
