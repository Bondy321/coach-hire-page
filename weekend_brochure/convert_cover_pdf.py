from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, unquote
import requests
import hashlib
import mimetypes
import shutil

HTML_FILE = Path("cover.html")

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
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()

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
    html = html_file.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    failed_images = []

    for img in soup.find_all("img"):
        src = img.get("src")

        if not src:
            continue

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


def main():
    if not HTML_FILE.exists():
        print(f"Could not find {HTML_FILE}. Make sure cover.html is in this folder.")
        return

    print(f"Processing: {HTML_FILE.name}")

    temp_html_path, failed_downloads = create_local_image_html_copy(HTML_FILE)

    output_file = OUTPUT_FOLDER / "cover.pdf"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=USER_AGENT,
            ignore_https_errors=True,
        )

        page = context.new_page()

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

        browser.close()

    shutil.rmtree(TEMP_HTML_FOLDER, ignore_errors=True)

    print(f"Created: {output_file}")

    if failed_downloads:
        print("\nImages that could not be downloaded:")
        for src, error in failed_downloads:
            print(f"- {src}")
            print(f"  {error}")

    if broken_images:
        print("\nImages still broken inside the PDF page:")
        for src in broken_images:
            print(f"- {src}")


if __name__ == "__main__":
    main()