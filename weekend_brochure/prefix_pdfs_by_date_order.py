from pathlib import Path
import csv
import shutil

CSV_FILE = Path("tours_in_date_order.csv")

PDF_FOLDER = Path("pdfs")
ORDERED_PDF_FOLDER = Path("ordered_pdfs")

ORDERED_PDF_FOLDER.mkdir(exist_ok=True)


def main():
    if not CSV_FILE.exists():
        print(f"Could not find CSV file: {CSV_FILE}")
        return

    if not PDF_FOLDER.exists():
        print(f"Could not find PDF folder: {PDF_FOLDER}")
        return

    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        print("The CSV file is empty.")
        return

    # Use at least 3 digits: 001, 002, 003...
    # If you ever had 1000+ tours, it would automatically use 4 digits.
    number_width = max(3, len(str(len(rows))))

    copied_count = 0
    missing_count = 0

    for index, row in enumerate(rows, start=1):
        html_file = row.get("HTML File", "").strip()

        if not html_file:
            print(f"Row {index}: No HTML File value found.")
            missing_count += 1
            continue

        html_path = Path(html_file)
        pdf_name = f"{html_path.stem}.pdf"

        source_pdf = PDF_FOLDER / pdf_name

        if not source_pdf.exists():
            print(f"Missing PDF for row {index}: {source_pdf}")
            missing_count += 1
            continue

        ordered_pdf_name = f"{index:0{number_width}d}_{source_pdf.name}"
        destination_pdf = ORDERED_PDF_FOLDER / ordered_pdf_name

        shutil.copy2(source_pdf, destination_pdf)

        print(f"Copied: {source_pdf.name} -> {ordered_pdf_name}")
        copied_count += 1

    print("")
    print(f"Done.")
    print(f"Copied PDFs: {copied_count}")
    print(f"Missing PDFs: {missing_count}")
    print(f"Ordered PDFs saved in: {ORDERED_PDF_FOLDER.resolve()}")


if __name__ == "__main__":
    main()