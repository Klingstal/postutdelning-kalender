import requests
from datetime import datetime, timedelta
from ics import Calendar, Event

# ---- KONFIG ----
API_KEY = "447ae136a7bad7f1849b3489e90edc45"
POSTNUMMER = "56632"
DAGAR_FRAMÅT = 90  # hur långt fram vi ska kolla
FILNAMN = "postutdelning.ics"
# ----------------

def hamta_utdelningsdagar():
    idag = datetime.today().strftime("%Y-%m-%d")
    slutdatum = (datetime.today() + timedelta(days=DAGAR_FRAMÅT)).strftime("%Y-%m-%d")
    
    url = (
        f"https://api2.postnord.com/rest/system/nps/v1/ppp/expose/sortpatterns/daterange"
        f"?apikey={API_KEY}"
        f"&fromdate={idag}"
        f"&todate={slutdatum}"
        f"&postcode={POSTNUMMER}"
    )

    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    
    dagar = []
    try:
        patterns = data["sortpatterns"]["deliverydays"]
        for d in patterns:
            datum = d["date"]
            dagar.append(datum)
    except KeyError:
        print("Fel: API-svaret har inte rätt struktur")
    
    return dagar

def skapa_ics(dagar):
    c = Calendar()
    for dag in dagar:
        e = Event()
        e.name = "Postutdelning"
        e.begin = dag
        e.make_all_day()
        c.events.add(e)
    
    with open(FILNAMN, "w", encoding="utf-8") as f:
        f.writelines(c)
    print(f"ICS-fil skapad: {FILNAMN}")

if __name__ == "__main__":
    dagar = hamta_utdelningsdagar()
    if dagar:
        skapa_ics(dagar)
    else:
        print("Inga dagar hittades.")
