from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
import re
import csv

# Folder containing your HTML files
FOLDER = Path(".")

# Change this if your no-year dates are for a different year
DEFAULT_YEAR_FOR_MISSING_DATES = 2026

OUTPUT_FILE = "tours_in_date_order.csv"

MONTHS = {
    "jan": "Jan",
    "january": "Jan",
    "feb": "Feb",
    "february": "Feb",
    "mar": "Mar",
    "march": "Mar",
    "apr": "Apr",
    "april": "Apr",
    "may": "May",
    "jun": "Jun",
    "june": "Jun",
    "jul": "Jul",
    "july": "Jul",
    "aug": "Aug",
    "august": "Aug",
    "sep": "Sep",
    "sept": "Sep",
    "september": "Sep",
    "oct": "Oct",
    "october": "Oct",
    "nov": "Nov",
    "november": "Nov",
    "dec": "Dec",
    "december": "Dec",
}


def clean_text(value):
    return " ".join(value.split()) if value else ""


def parse_tour_date(date_text):
    """
    Handles formats like:
    Fri 12th Feb '27
    Fri 12th Feb 2027
    Sat 11th Jul
    Fri 26th Jun
    Mon 5 Oct, 2026
    """

    original = clean_text(date_text)

    if not original:
        return None

    text = original.replace(",", "")

    # Remove ordinal endings: 1st, 2nd, 3rd, 4th, etc
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text, flags=re.IGNORECASE)

    # Convert '27 into 2027
    text = re.sub(r"'(\d{2})", r"20\1", text)

    parts = text.split()

    # Remove weekday if present
    # Example: Fri 12 Feb 2027 becomes 12 Feb 2027
    if parts and re.match(r"^(mon|tue|wed|thu|fri|sat|sun)", parts[0], re.IGNORECASE):
        parts = parts[1:]

    # Now we expect:
    # 12 Feb 2027
    # 12 Feb
    if len(parts) < 2:
        return None

    day = parts[0]
    month = parts[1]
    year = parts[2] if len(parts) >= 3 else str(DEFAULT_YEAR_FOR_MISSING_DATES)

    month_clean = MONTHS.get(month.lower())

    if not month_clean:
        return None

    date_string = f"{day} {month_clean} {year}"

    try:
        return datetime.strptime(date_string, "%d %b %Y")
    except ValueError:
        return None


def extract_tour_info(html_file):
    html = html_file.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    title = clean_text(h1.get_text()) if h1 else html_file.stem

    duration_tag = soup.select_one(".duration-badge")
    duration = clean_text(duration_tag.get_text()) if duration_tag else ""

    from_price_tag = soup.select_one(".header-price")
    from_price = clean_text(from_price_tag.get_text()) if from_price_tag else ""

    deposit_tag = soup.select_one(".deposit-highlight")
    deposit = clean_text(deposit_tag.get_text()) if deposit_tag else ""

    booking_link = ""
    link = soup.select_one(".footer-cta a[href]")
    if link:
        booking_link = link.get("href", "")

    date_rows = soup.select(".date-item")
    parsed_dates = []

    for row in date_rows:
        date_tag = row.select_one(".dt-date")
        price_tag = row.select_one(".dt-price")

        if not date_tag:
            continue

        raw_date = clean_text(date_tag.get_text())
        parsed_date = parse_tour_date(raw_date)

        if not parsed_date:
            continue

        date_price = clean_text(price_tag.get_text()) if price_tag else ""

        parsed_dates.append({
            "raw_date": raw_date,
            "parsed_date": parsed_date,
            "price": date_price
        })

    if not parsed_dates:
        return None

    parsed_dates.sort(key=lambda item: item["parsed_date"])
    first_date = parsed_dates[0]

    all_dates = "; ".join(
        f"{item['parsed_date'].strftime('%d %B %Y')} - {item['price']}"
        for item in parsed_dates
    )

    return {
        "sort_date": first_date["parsed_date"],
        "first_date": first_date["parsed_date"].strftime("%d %B %Y"),
        "tour_name": title,
        "first_date_price": first_date["price"],
        "from_price": from_price,
        "duration": duration,
        "deposit": deposit,
        "all_dates": all_dates,
        "booking_link": booking_link,
        "file_name": html_file.name
    }


def main():
    tours = []
    failed_files = []

    for html_file in FOLDER.glob("*.html"):
        tour = extract_tour_info(html_file)

        if tour:
            tours.append(tour)
        else:
            failed_files.append(html_file.name)

    tours.sort(key=lambda item: item["sort_date"])

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as file:
        fieldnames = [
            "First Date",
            "Tour Name",
            "Price On First Date",
            "From Price",
            "Duration",
            "Deposit",
            "All Dates",
            "Booking Link",
            "HTML File"
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for tour in tours:
            writer.writerow({
                "First Date": tour["first_date"],
                "Tour Name": tour["tour_name"],
                "Price On First Date": tour["first_date_price"],
                "From Price": tour["from_price"],
                "Duration": tour["duration"],
                "Deposit": tour["deposit"],
                "All Dates": tour["all_dates"],
                "Booking Link": tour["booking_link"],
                "HTML File": tour["file_name"]
            })

    print(f"Done. Created: {OUTPUT_FILE}")
    print(f"Found {len(tours)} tours.")

    if failed_files:
        print("\nFiles where no readable dates were found:")
        for file_name in failed_files:
            print(f"- {file_name}")


if __name__ == "__main__":
    main()