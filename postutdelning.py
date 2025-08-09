import requests
import datetime
from icalendar import Calendar, Event

# --- KONFIGURATION ---
POSTNUMMER = "56632"
API_KEY = "447ae136a7bad7f1849b3489e90edc45"

# --- Datumintervall ---
idag = datetime.date.today()
slutdatum = idag + datetime.timedelta(days=90)

# --- API-endpoint för utdelningsperiod ---
url = f"https://api2.postnord.com/rest/nextdays/v1/deliverydays/{POSTNUMMER}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "User-Agent": "python-script"
}

params = {
    "fromDate": idag.strftime("%Y-%m-%d"),
    "toDate": slutdatum.strftime("%Y-%m-%d")
}

response = requests.get(url, headers=headers, params=params)
response.raise_for_status()
data = response.json()

# --- Skapa kalender ---
cal = Calendar()
cal.add("prodid", "-//Postutdelning//SE")
cal.add("version", "2.0")

# --- Lägg till alla utdelningsdagar ---
for day in data.get("deliveryDays", []):
    dt = datetime.datetime.strptime(day, "%Y-%m-%d").date()
    event = Event()
    event.add("summary", "Postutdelning 📬")
    event.add("dtstart", dt)
    event.add("dtend", dt + datetime.timedelta(days=1))
    event.add("dtstamp", datetime.datetime.now())
    cal.add_component(event)

# --- Spara kalenderfil ---
with open("docs/postutdelning.ics", "wb") as f:
    f.write(cal.to_ical())

print(f"Kalenderfil skapad med {len(data.get('deliveryDays', []))} utdelningsdagar.")
