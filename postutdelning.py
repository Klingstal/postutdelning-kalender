import requests
import datetime
from icalendar import Calendar, Event

POSTNUMMER = "56632"
url = f"https://portal.postnord.com/api/sendoutarrival/{POSTNUMMER}"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)
response.raise_for_status()
data = response.json()

cal = Calendar()
cal.add("prodid", "-//Postutdelning//SE")
cal.add("version", "2.0")

for day in data.get("deliveryDays", []):
    dt = datetime.datetime.strptime(day, "%Y-%m-%d").date()
    event = Event()
    event.add("summary", "Postutdelning 📬")
    event.add("dtstart", dt)
    event.add("dtend", dt + datetime.timedelta(days=1))
    event.add("dtstamp", datetime.datetime.now())
    cal.add_component(event)

with open("public/postutdelning.ics", "wb") as f:
    f.write(cal.to_ical())

