import requests
import json
import time
import logging
import os

# === KONFIGURATION ===
API_KEY = "447ae136a7bad7f1849b3489e90edc45"
CACHE_FILE = "health_cache.json"
CACHE_TTL = 3600  # sekunder (1 timme)
LOG_FILE = "health_check.log"

# === LOGGNING ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Om datan är gammal, returnera None
            if time.time() - data.get("timestamp", 0) < CACHE_TTL:
                return data.get("response")
        except Exception as e:
            logging.warning(f"Kunde inte läsa cache: {e}")
    return None

def save_cache(response):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time(), "response": response}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"Kunde inte spara cache: {e}")

def health_check():
    # Försök använda cache först
    cached = load_cache()
    if cached:
        logging.info("Använder cachead data")
        return cached

    url = f"https://host/rest/location/v1/surcharge/manage/health?apikey={API_KEY}"
    try:
        logging.info(f"Anropar: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        save_cache(data)
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Nätverksfel: {e}")
    except Exception as e:
        logging.error(f"Oväntat fel: {e}")
    return None

def main():
    result = health_check()
    if result:
        logging.info(f"API-svar: {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        logging.error("Kunde inte hämta data.")

if __name__ == "__main__":
    main()
