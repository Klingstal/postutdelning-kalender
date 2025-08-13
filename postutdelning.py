import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import os
import sys

# ===== KONFIGURATION =====
API_KEY = os.environ.get("POSTNORD_API_KEY", "DIN_API_NYCKEL_HÄR")
POSTNUMMER = "24600"  # Ändra till ditt postnummer
ANTAL_DAGAR_FRAMÅT = 60  # Hur långt fram i tiden kalendern ska innehålla utdelningsdagar
ICS_FIL = "docs/postutdelning.ics"

# ===== GEMENSAM HEADER =====
HEADERS = {"apikey": API_KEY}

# ===== HÄMTA POSTNUMMER-TYP (X, Y, S) =====
def get_postnummer_typ(postnummer):
    url = f"https://api2.postnord.com/rest/masterdata/gim/v2/postalcode?ids=postalcode:{postnummer}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    try:
        return data["postalCodes"][0]["mailingPostalCodeType"]
    except (KeyError, IndexError):
        raise ValueError(f"Kunde inte hämta posttyp för {postnummer}")

# ===== HÄMTA DAGSTYPER (X, Y, H) FÖR DATUMINTERVALL =====
def get_sort_patterns(from_date, to_date):
    url = (
        f"https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
        f"?fromdate={from_date}&todate={to_date}"
    )
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    result = {}
    try:
        for item in data.get("sortPatterns", []):
            result[item["date"]] = item["pattern"]
    except (KeyError, TypeError):
        raise ValueError("Felaktigt svar från sortpatterns API")
    return result

# ===== BESTÄM UTDAGNAR =====
def calculate_delivery_days(postnummer_typ, sort_patterns):
    days = []
    for date_str, pattern in sort_patterns.items():
        if pattern == "H":
            continue  # Helgdag, ingen utdelning
        if postnummer_typ == "S":
            days.append(date_str)  # S = utdelning varje vardag
        elif postnummer_typ == pattern:
            days.append(date_str)  # Matchar X- eller Y-dag
    return days

# ===== SKAPA ICS =====
def create_ics(delivery_days):
    cal = Calendar()
    cal.add("prodid", "-//Postutdelning//PostNord//")
    cal.add("version", "2.0")

    for day_str in delivery_days:
        day_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        event = Event()
        event.add("summary", "Postutdelning")
        event.add("dtstart", day_date)
        event.add("dtend", day_date + timedelta(days=1))
        event.add("description", "Brevutdelning enligt PostNord")
        cal.add_component(event)

    os.makedirs(os.path.dirname(ICS_FIL), exist_ok=True)
    with open(ICS_FIL, "wb") as f:
        f.write(cal.to_ical())

# ===== HUVUDKÖRNING =====
if __name__ == "__main__":
    if not API_KEY or API_KEY == "DIN_API_NYCKEL_HÄR":
        print("❌ API-nyckel saknas. Sätt miljövariabeln POSTNORD_API_KEY.")
        sys.exit(1)

    today = datetime.today().date()
    end_date = today + timedelta(days=ANTAL_DAGAR_FRAMÅT)

    try:
        post_typ = get_postnummer_typ(POSTNUMMER)
        print(f"📦 Postnummer {POSTNUMMER} har typ {post_typ}")

        patterns = get_sort_patterns(today.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        delivery_days = calculate_delivery_days(post_typ, patterns)

        print(f"📅 Utdelningsdagar ({len(delivery_days)} dagar): {delivery_days}")

        create_ics(delivery_days)
        print(f"✅ ICS-fil skapad: {ICS_FIL}")

    except requests.HTTPError as e:
        print(f"❌ HTTP-fel: {e} - Svar: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fel: {e}")
        sys.exit(1)
