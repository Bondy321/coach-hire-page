from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, unquote
import requests
import hashlib
import mimetypes
import shutil

INPUT_FOLDER = Path(".")
OUTPUT_FOLDER = Path("pdfs")
IMAGE_CACHE_FOLDER = Path("_downloaded_images")
TEMP_HTML_FOLDER = Path("_temp_html_for_pdf")

OUTPUT_FOLDER.mkdir(exist_ok=True)
IMAGE_CACHE_FOLDER.mkdir(exist_ok=True)
TEMP_HTML_FOLDER.mkdir(exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def safe_file_extension(url, response):
    """
    Work out the best image file extension.
    Uses the original URL where possible, then falls back to the content type.
    """

    parsed_url = urlparse(url)
    original_suffix = Path(unquote(parsed_url.path)).suffix.lower()

    if original_suffix in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
        return original_suffix

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
    guessed_extension = mimetypes.guess_extension(content_type)

    if guessed_extension:
        return guessed_extension

    return ".jpg"


def download_image(url):
    """
    Downloads an image and returns the local file path.
    If it has already been downloaded, it reuses the cached copy.
    """

    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()

    # If we have already downloaded this image, reuse it
    existing_matches = list(IMAGE_CACHE_FOLDER.glob(f"{url_hash}.*"))
    if existing_matches:
        return existing_matches[0]

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://lochlomondtravel.com/",
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    extension = safe_file_extension(url, response)
    local_image_path = IMAGE_CACHE_FOLDER / f"{url_hash}{extension}"

    local_image_path.write_bytes(response.content)

    return local_image_path


def create_local_image_html_copy(html_file):
    """
    Creates a temporary copy of the HTML file where remote image URLs
    are replaced with local downloaded image paths.
    """

    html = html_file.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    failed_images = []

    for img in soup.find_all("img"):
        src = img.get("src")

        if not src:
            continue

        # Only download online images
        if src.startswith("http://") or src.startswith("https://"):
            try:
                local_image_path = download_image(src)
                img["src"] = local_image_path.resolve().as_uri()
            except Exception as error:
                failed_images.append((src, str(error)))

    temp_html_path = TEMP_HTML_FOLDER / html_file.name
    temp_html_path.write_text(str(soup), encoding="utf-8")

    return temp_html_path, failed_images


def wait_for_images(page):
    """
    Waits until all images on the page are either loaded successfully
    or clearly failed. Then returns any broken image URLs.
    """

    return page.evaluate(
        """
        async () => {
            const images = Array.from(document.images);

            await Promise.all(images.map(img => {
                if (img.complete) return Promise.resolve();

                return new Promise(resolve => {
                    img.addEventListener('load', resolve, { once: true });
                    img.addEventListener('error', resolve, { once: true });
                });
            }));

            return images
                .filter(img => !img.complete || img.naturalWidth === 0)
                .map(img => img.src);
        }
        """
    )


def convert_html_to_pdf(page, original_html_file):
    print(f"Processing: {original_html_file.name}")

    temp_html_path, failed_downloads = create_local_image_html_copy(original_html_file)

    output_file = OUTPUT_FOLDER / f"{original_html_file.stem}.pdf"

    page.goto(temp_html_path.resolve().as_uri(), wait_until="load", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)

    broken_images = wait_for_images(page)

    page.pdf(
        path=str(output_file),
        format="A4",
        print_background=True,
        prefer_css_page_size=True,
        margin={
            "top": "0mm",
            "right": "0mm",
            "bottom": "0mm",
            "left": "0mm",
        },
    )

    print(f"Created: {output_file}")

    if failed_downloads:
        print("Images that could not be downloaded:")
        for src, error in failed_downloads:
            print(f" - {src}")
            print(f"   {error}")

    if broken_images:
        print("Images still broken inside the PDF page:")
        for src in broken_images:
            print(f" - {src}")

    print("")


def main():
    html_files = sorted(INPUT_FOLDER.glob("*.html"))

    if not html_files:
        print("No HTML files found in this folder.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=USER_AGENT,
            ignore_https_errors=True,
        )

        page = context.new_page()

        for html_file in html_files:
            convert_html_to_pdf(page, html_file)

        browser.close()

    print(f"Done. Created PDFs for {len(html_files)} HTML files.")
    print(f"PDFs are saved in: {OUTPUT_FOLDER.resolve()}")

    # Optional: delete temporary HTML copies after finishing
    # The downloaded images are kept so future runs are faster.
    shutil.rmtree(TEMP_HTML_FOLDER, ignore_errors=True)


if __name__ == "__main__":
    main()