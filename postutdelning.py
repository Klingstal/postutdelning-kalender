import requests
import datetime
from icalendar import Calendar, Event
import os
import time

# --- KONFIGURATION ---
POSTNUMMER = "56632"
API_KEY = "447ae136a7bad7f1849b3489e90edc45"

# --- Datumintervall ---
idag = datetime.date.today()
slutdatum = idag + datetime.timedelta(days=90)

# --- Hämta postnummer-typ (X, Y eller S) med retry vid 429 ---
def get_postalcode_info(postnummer):
    url = "https://api2.postnord.com/rest/masterdata/gim/v2/postalcode"
    params = {
        "apikey": API_KEY,
        "ids": f"postalcode:{postnummer}"
    }
    attempts = 5
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"Postnummerdata: {data}")  # debug
            return data
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = 10
                print(f"Rate limit reached (429). Väntar {wait} sekunder och försöker igen... (försök {attempt+1} av {attempts})")
                time.sleep(wait)
            else:
                print(f"HTTPError vid hämtning av postnummerinfo: {e}")
                raise
    raise Exception("Misslyckades hämta postnummerinfo efter flera försök")

# --- Hämta sorteringsmönster (X, Y eller H dagar) med retry vid 429 ---
def get_sortpatterns(from_date, to_date):
    url = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
    params = {
        "apikey": API_KEY,
        "fromdate": from_date.strftime("%Y-%m-%d"),
        "todate": to_date.strftime("%Y-%m-%d")
    }
    attempts = 5
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            print(f"Sorteringsmönsterdata: {data}")  # debug
            return data
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = 10
                print(f"Rate limit reached (429). Väntar {wait} sekunder och försöker igen... (försök {attempt+1} av {attempts})")
                time.sleep(wait)
            else:
                print(f"HTTPError vid hämtning av sorteringsmönster: {e}")
                raise
    raise Exception("Misslyckades hämta sorteringsmönster efter flera försök")

# --- Tolka vilka dagar som är utdelningsdagar för postnumret ---
def calculate_delivery_days(postalcode_info, sortpatterns):
    # Hämta typen av postnummer (X, Y eller S)
    postnummer_typ = None
    if postalcode_info and len(postalcode_info) > 0:
        postnummer_typ = postalcode_info[0].get("postalCodeType", None)
    print(f"Postnummertyp: {postnummer_typ}")

    utdelningsdagar = []
    for pattern in sortpatterns:
        pattern_name = pattern.get("patternName", None)
        planned_date = pattern.get("plannedDate", None)
        if planned_date is None or pattern_name is None:
            continue
        # Regler enligt PostNord:
        # - Postnummertyp S får utdelning varje dag (lägger till alla dagar som inte är H)
        # - Postnummertyp X får utdelning på X dagar
        # - Postnummertyp Y får utdelning på Y dagar
        # - H = helgdag/ingen utdelning
        if pattern_name == "H":
            # ingen utdelning denna dag
            continue
        if postnummer_typ == "S":
            utdelningsdagar.append(planned_date)
        elif postnummer_typ == pattern_name:
            utdelningsdagar.append(planned_date)

    return utdelningsdagar

def main():
    # Hämta data från API
    postalcode_info = get_postalcode_info(POSTNUMMER)
    sortpatterns = get_sortpatterns(idag, slutdatum)

    # Beräkna utdelningsdagar
    utdelningsdagar = calculate_delivery_days(postalcode_info, sortpatterns)
    print(f"Utdelningsdagar (totalt {len(utdelningsdagar)}): {utdelningsdagar}")

    # Skapa kalender
    cal = Calendar()
    cal.add("prodid", "-//Postutdelning//SE")
    cal.add("version", "2.0")

    for day in utdelningsdagar:
        dt = datetime.datetime.strptime(day, "%Y-%m-%d").date()
        event = Event()
        event.add("summary", "Postutdelning 📬")
        event.add("dtstart", dt)
        event.add("dtend", dt + datetime.timedelta(days=1))
        event.add("dtstamp", datetime.datetime.now())
        cal.add_component(event)

    # Spara kalenderfil
    os.makedirs("docs", exist_ok=True)
    with open("docs/postutdelning.ics", "wb") as f:
        f.write(cal.to_ical())

    print(f"Kalenderfil skapad med {len(utdelningsdagar)} utdelningsdagar.")

if __name__ == "__main__":
    main()
