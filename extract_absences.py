#!/usr/bin/env python3
"""Extract absences from absences.html (spielerplus.de) into absences.csv."""

import re
import html
import csv
import sys
from datetime import date

INPUT_FILE = "absences.html"
OUTPUT_FILE = "absences.csv"
FUTURE_VACATIONS_FILE = "future_vacations.csv"
TODAY = date.today()

# Tab id -> category name
TAB_NAMES = {
    "absence-tab0": "Aktuell",
    "absence-tab1": "Urlaub",
    "absence-tab2": "Krank/Verletzt",
    "absence-tab3": "Inaktiv",
    "absence-tab4": "Sonstige",
    "absence-tab5": "1 Tag in der Woche",
}


def extract_real_html(filepath: str) -> str:
    """The file is a Chrome view-source page; extract the original HTML from it."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = re.findall(r'<td class="line-content">(.*?)</td>', content)
    real_html = ""
    for line in lines:
        text = re.sub(r"<[^>]+>", "", line)
        text = html.unescape(text)
        real_html += text + "\n"
    return real_html


def get_text(match_str: str) -> str:
    """Strip tags and clean whitespace from an HTML fragment."""
    text = re.sub(r"<[^>]+>", "", match_str)
    return " ".join(text.split())


def extract_absences(real_html: str) -> list[dict]:
    records = []

    # Split into tab pane sections
    tab_sections = re.split(r'<div id="(absence-tab\d+)"', real_html)
    # tab_sections: [before, tab_id, content, tab_id, content, ...]
    i = 1
    while i < len(tab_sections) - 1:
        tab_id = tab_sections[i]
        section_html = tab_sections[i + 1]
        category = TAB_NAMES.get(tab_id, tab_id)
        i += 2

        # Extract individual list items
        items = re.split(r"<!-- LIST-ITEM INDEX -->", section_html)
        for item in items[1:]:  # first element is before the first marker
            # Name
            name_match = re.search(r'<div class="list-label">(.*?)</div>', item, re.DOTALL)
            name = get_text(name_match.group(1)) if name_match else ""

            # Reason / note (hidden-xs sublabel = full text, not duplicated with date)
            reason_match = re.search(
                r'<div class="list-sublabel hidden-xs">(.*?)</div>', item, re.DOTALL
            )
            reason = get_text(reason_match.group(1)) if reason_match else ""

            # Date range
            date_match = re.search(
                r'<div class="list-value[^"]*">(.*?)</div>', item, re.DOTALL
            )
            dates = get_text(date_match.group(1)) if date_match else ""

            # User ID from profile link
            uid_match = re.search(r'/user/view\?id=(\d+)', item)
            user_id = uid_match.group(1) if uid_match else ""

            if name:
                records.append(
                    {
                        "category": category,
                        "name": name,
                        "dates": dates,
                        "reason": reason,
                        "user_id": user_id,
                    }
                )

    return records


def parse_end_date(dates_str: str) -> date | None:
    """Parse the end date from 'DD.MM - DD.MM.YY' or 'ab DD.MM.YY' formats."""
    dates_str = dates_str.strip()
    # Range format: "DD.MM - DD.MM.YY"
    m = re.search(r'-\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*$', dates_str)
    if m:
        e_day, e_month, yr = m.groups()
        yr = int(yr)
        year = 2000 + yr if yr < 100 else yr
        return date(year, int(e_month), int(e_day))
    # Open-ended: "ab DD.MM.YY" — treat as ongoing (no end date)
    return None


def filter_future_vacations(records: list[dict]) -> list[dict]:
    """Return Urlaub entries whose end date is today or in the future."""
    future = [
        r for r in records
        if r["category"] == "Urlaub"
        and (end := parse_end_date(r["dates"])) is not None
        and end >= TODAY
    ]
    future.sort(key=lambda r: parse_end_date(r["dates"]))
    return future


def main():
    try:
        real_html = extract_real_html(INPUT_FILE)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.", file=sys.stderr)
        sys.exit(1)

    records = extract_absences(real_html)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "name", "dates", "reason", "user_id"])
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {len(records)} records to {OUTPUT_FILE}")

    future = filter_future_vacations(records)
    with open(FUTURE_VACATIONS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "name", "dates", "reason", "user_id"])
        writer.writeheader()
        writer.writerows(future)

    print(f"Wrote {len(future)} future vacations to {FUTURE_VACATIONS_FILE}")


if __name__ == "__main__":
    main()
