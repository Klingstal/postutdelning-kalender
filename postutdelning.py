import requests
from datetime import datetime, timedelta
from pathlib import Path

POSTNUMMER = "56632"
URL = f"https://portal.postnord.com/api/sendoutarrival/{POSTNUMMER}"
ical_lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Klingstal//Postutdelning//EN"
]

response = requests.get(URL)
response.raise_for_status()
data = response.json()
dates = data.get("dates", [])[:2]  # De två närmaste dagarna

for date_str in dates:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt_start = dt.strftime("%Y%m%d")
    dt_end = (dt + timedelta(days=1)).strftime("%Y%m%d")

    ical_lines += [
        "BEGIN:VEVENT",
        f"DTSTART;VALUE=DATE:{dt_start}",
        f"DTEND;VALUE=DATE:{dt_end}",
        f"SUMMARY:Postutdelning",
        "END:VEVENT"
    ]

ical_lines.append("END:VCALENDAR")

Path("docs/postutdelning.ics").write_text("\n".join(ical_lines), encoding="utf-8")

