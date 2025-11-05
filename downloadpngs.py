import os
import re
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# === CONFIGURATION ===
url = "https://www.realmeye.com/wiki/loot-containers"
output_dir = "downloaded_pngs"

# === SETUP SELENIUM (Headless Chrome) ===
options = Options()
options.add_argument("--headless=new")  # run without UI
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0.0.0 Safari/537.36")

print("Launching Chrome headless browser...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# === FETCH PAGE ===
print(f"Fetching page: {url}")
driver.get(url)
time.sleep(3)  # wait for JS to load

html = driver.page_source
driver.quit()

# === PARSE HTML ===
soup = BeautifulSoup(html, "html.parser")
os.makedirs(output_dir, exist_ok=True)

download_tasks = []

for a_tag in soup.find_all("a", title=True):
    img_tag = a_tag.find("img")
    if img_tag and img_tag.get("src", "").lower().endswith(".png"):
        img_url = urljoin(url, img_tag["src"])
        title = a_tag["title"]
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        filename = f"{safe_title}.png"
        download_tasks.append((img_url, filename))

print(f"Found {len(download_tasks)} PNGs.")

# === DOWNLOAD PNGs ===
for i, (img_url, filename) in enumerate(download_tasks, start=1):
    filepath = os.path.join(output_dir, filename)
    try:
        r = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(r.content)
        print(f"[{i}] ✅ {filename}")
    except Exception as e:
        print(f"[{i}] ❌ Failed to download {img_url}: {e}")

print(f"\n✅ Done! {len(download_tasks)} images downloaded to '{output_dir}/'.")
