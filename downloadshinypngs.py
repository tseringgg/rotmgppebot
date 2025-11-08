# download_all_sprites_persistent_session.py
import os
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

HTML_FILE = "rotmg_shinies.html"
ORIGINAL_DIR = "sprites"
SHINY_DIR = "shiny_sprites"
BASE_URL = "https://www.realmeye.com/s/a/img/wiki/i/"

# Where Chrome profile will be stored (persistent cookies/session)
CHROME_PROFILE_DIR = os.path.abspath("./chrome_profile")

def setup_driver():
    chrome_options = Options()

    # Use a persistent profile so cookies/localStorage persist across runs.
    chrome_options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")

    # Headless is optional; you can remove --headless while debugging.
    chrome_options.add_argument("--headless=new")  # use new headless mode if supported
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Keep browser UA stable
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )

    # If chromedriver isn't on PATH, pass executable_path to webdriver.Chrome()
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def parse_html():
    """Extract both original and shiny image URLs with names from local HTML."""
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    items = []
    for table in soup.find_all("table", class_="table"):
        for row in table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            item_tag = cols[0].find("a")
            item_name = item_tag.text.strip() if item_tag else None
            if not item_name:
                continue

            original_img = cols[1].find("img")
            shiny_img = cols[2].find("img")

            def get_url(img):
                if img and img.get("src", "").endswith(".png"):
                    return f"{BASE_URL}/{os.path.basename(img['src'].lstrip('/'))}"
                return None

            items.append({
                "name": item_name,
                "original": get_url(original_img),
                "shiny": get_url(shiny_img)
            })
    return items

def safe_filename(name):
    return (
        name.replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace("?", "")
            .replace("*", "")
            .replace('"', "")
    )

def selenium_cookies_to_requests_session(driver):
    """Create a requests.Session populated with cookies from Selenium driver."""
    sess = requests.Session()
    # Pull UA from the browser
    try:
        ua = driver.execute_script("return navigator.userAgent;")
    except Exception:
        ua = "Mozilla/5.0"
    sess.headers.update({"User-Agent": ua, "Referer": BASE_URL})
    # Add all cookies from the browser to the requests session
    for c in driver.get_cookies():
        # requests accepts cookie as requests.cookies.create_cookie
        sess.cookies.set(c["name"], c["value"], domain=c.get("domain", None), path=c.get("path", "/"))
    return sess

def download_with_persistent_session(driver, url, save_path, label, sess):
    """
    Use the provided requests.Session (seeded with Selenium cookies/UA)
    to download a URL and save to disk. No retries here (per request).
    """
    try:
        # Navigate browser first to emulate a real visit (helps Cloudflare)
        driver.get(url)
        # small wait to let browser handshake; keep minimal
        time.sleep(0.8)

        # Update session cookies in case navigation changed cookies
        for c in driver.get_cookies():
            sess.cookies.set(c["name"], c["value"], domain=c.get("domain", None), path=c.get("path", "/"))

        r = sess.get(url, stream=True, timeout=15)
        if r.status_code == 200:
            with open(save_path, "wb") as f_out:
                for chunk in r.iter_content(1024):
                    if chunk:
                        f_out.write(chunk)
            print(f"✅ Downloaded {label}")
            return True
        else:
            print(f"❌ Failed {label} (HTTP {r.status_code}) | {url}")
            return False
    except Exception as e:
        print(f"⚠️ Error downloading {label}: {e}")
        return False

def download_all_sprites():
    os.makedirs(ORIGINAL_DIR, exist_ok=True)
    os.makedirs(SHINY_DIR, exist_ok=True)

    items = parse_html()
    print(f"Found {len(items)} items in HTML")

    driver = setup_driver()
    # Optionally open the site root once to prime cookies (and to allow you to login manually
    # if running non-headless). This helps build a persistent session on first run.
    try:
        driver.get(BASE_URL)
        time.sleep(1.0)
    except Exception as e:
        print("⚠️ Error opening base URL in Selenium:", e)

    # create requests session seeded from driver cookies/UA
    sess = selenium_cookies_to_requests_session(driver)

    total, failed = 0, 0
    # Optional small delay between downloads to be polite — set to 0 if you want no delay.
    POLITE_DELAY = 0.5  # seconds

    for item in items:
        base_name = safe_filename(item["name"])

        # original sprite
        if item["original"]:
            orig_path = os.path.join(ORIGINAL_DIR, f"{base_name}.png")
            if not os.path.exists(orig_path):
                ok = download_with_persistent_session(driver, item["original"], orig_path, f"{base_name} (original)", sess)
                if ok:
                    total += 1
                else:
                    failed += 1
                time.sleep(POLITE_DELAY)

        # shiny sprite
        if item["shiny"]:
            shiny_path = os.path.join(SHINY_DIR, f"{base_name} (shiny).png")
            if not os.path.exists(shiny_path):
                ok = download_with_persistent_session(driver, item["shiny"], shiny_path, f"{base_name} (shiny)", sess)
                if ok:
                    total += 1
                else:
                    failed += 1
                time.sleep(POLITE_DELAY)

    driver.quit()
    print(f"\n✅ Finished! {total} images downloaded, {failed} failed.")

if __name__ == "__main__":
    download_all_sprites()
