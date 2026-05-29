from pathlib import Path
from playwright.sync_api import sync_playwright

INPUT_FOLDER = Path(".")
OUTPUT_FOLDER = Path("pdfs")

OUTPUT_FOLDER.mkdir(exist_ok=True)

def convert_html_to_pdf(page, html_file):
    output_file = OUTPUT_FOLDER / f"{html_file.stem}.pdf"

    file_url = html_file.resolve().as_uri()

    page.goto(file_url, wait_until="networkidle")

    page.pdf(
        path=str(output_file),
        format="A4",
        print_background=True,
        margin={
            "top": "0mm",
            "right": "0mm",
            "bottom": "0mm",
            "left": "0mm",
        }
    )

    print(f"Created: {output_file}")

def main():
    html_files = sorted(INPUT_FOLDER.glob("*.html"))

    if not html_files:
        print("No HTML files found.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        for html_file in html_files:
            convert_html_to_pdf(page, html_file)

        browser.close()

    print(f"\nDone. Created {len(html_files)} PDFs in the '{OUTPUT_FOLDER}' folder.")

if __name__ == "__main__":
    main()