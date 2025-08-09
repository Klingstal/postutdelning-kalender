import requests
import datetime
from icalendar import Calendar, Event
import os

# --- KONFIGURATION ---
POSTNUMMER = "56632"  # Ditt postnummer
API_KEY = "447ae136a7bad7f1849b3489e90edc45"  # Din API-nyckel

# --- Datumintervall ---
idag = datetime.date.today()
slutdatum = idag + datetime.timedelta(days=90)

# --- Hämta sorteringsmönster (X, Y, H) ---
sortpatterns_url = "https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
params_sort = {
    "apikey": API_KEY,
    "fromdate": idag.strftime("%Y-%m-%d"),
    "todate": slutdatum.strftime("%Y-%m-%d")
}
r = requests.get(sortpatterns_url, params=params_sort)
r.raise_for_status()
sortpatterns = r.json()

# --- Hämta postnummer-typ (X, Y eller S) ---
postalcode_url = "https://api2.postnord.com/rest/masterdata/gim/v2/postalcode"
params_postal = {
    "apikey": API_KEY,
    "ids": f"postalcode:{POSTNUMMER}"
}
r2 = requests.get(postalcode_url, params=params_postal)
r2.raise_for_status()
postalcode_data = r2.json()

# Extrahera postnummer-typ
postnummer_typ = None
if "postalCodes" in postalcode_data and len(postalcode_data["postalCodes"]) > 0:
    postnummer_typ = postalcode_data["postalCodes"][0].get("type")
else:
    raise ValueError("Postnummer saknas eller ogiltigt i API-svaret")

print(f"Postnummer {POSTNUMMER} är av typ: {postnummer_typ}")

# --- Beräkna utdelningsdagar ---
utdelningsdagar = []
for pattern in sortpatterns:
    datum = pattern['plannedDate']       # Datum som str "YYYY-MM-DD"
    sort_type = pattern['patternName']   # T.ex. "X", "Y", "H"
    if sort_type == 'H':
        # Ingen utdelning på helg/helgdagar
        continue
    if postnummer_typ == 'S' or sort_type == postnummer_typ:
        utdelningsdagar.append(datum)

print(f"Antal utdelningsdagar hittade: {len(utdelningsdagar)}")

# --- Skapa kalender ---
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

# --- Spara kalenderfil ---
os.makedirs("docs", exist_ok=True)
kalenderfil = "docs/postutdelning.ics"
with open(kalenderfil, "wb") as f:
    f.write(cal.to_ical())

print(f"Kalenderfil skapad: {kalenderfil}")
