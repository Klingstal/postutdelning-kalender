import requests
import json
import time
import logging
from pathlib import Path

# --- Konfiguration ---
API_KEY = "DIN_API_KEY"
BASE_URL = "https://exempel.com/rest/location/v1/surcharge/manage"
CACHE_FILE = Path("health_cache.json")
LOG_FILE = "script.log"

# --- Logging ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def fetch_health():
    """Hämtar hälsostatus från API:t med caching och felhantering."""
    # Kolla cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                # Om cachen är mindre än 1 timme gammal, använd den
                if time.time() - data["timestamp"] < 3600:
                    logging.info("Använder cache-data för health check.")
                    return data["response"]
        except Exception as e:
            logging.warning(f"Cache-läsfel: {e}")

    # Hämtar från API
    url = f"{BASE_URL}/health?apikey={API_KEY}"
    while True:
        try:
            logging.info(f"Hämtar health check från {url}")
            response = requests.get(url, timeout=10)
            if response.status_code == 429:
                logging.warning("API-limit nådd. Väntar 60 sek...")
                time.sleep(60)
                continue
            response.raise_for_status()
            result = response.json()

            # Spara i cache
            with open(CACHE_FILE, "w") as f:
                json.dump({"timestamp": time.time(), "response": result}, f)

            logging.info("Health check hämtad och cachad.")
            return result
        except requests.RequestException as e:
            logging.error(f"Fel vid API-anrop: {e}")
            time.sleep(10)

def main():
    health_data = fetch_health()
    print(json.dumps(health_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
