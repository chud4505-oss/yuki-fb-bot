import json
import os
import requests
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
FB_COOKIES_RAW = os.environ.get("FB_COOKIES", "")
BOT_NAME = "Yuki 2 (VAA)"
HISTORY_FILE = "seen_gh_posts.json"

PAGE_URLS = [
    "https://www.facebook.com/drd.vau",
    "https://www.facebook.com/doanhoi.khoangoaingu.vaa",
    "https://www.facebook.com/doanhoikhoakythuathangkhong",
    "https://www.facebook.com/doanhoikhoakhaithachangkhong",
    "https://www.facebook.com/vaa.doanhoikhoaquantrikinhdoanh",
    "https://www.facebook.com/profile.php?id=61576624683756",
    "https://www.facebook.com/doanhoi.kinhtehangkhong.vaa",
    "https://www.facebook.com/DoanTNHoiSV.VAU",
    "https://www.facebook.com/ftas.vaa.vn",
    "https://www.facebook.com/khoangoainguVAA",
    "https://www.facebook.com/clblyluantrevaa",
    "https://www.facebook.com/profile.php?id=100092618240008",
    "https://www.facebook.com/3e.vaaec",
    "https://www.facebook.com/VolleyballClub.VAA",
    "https://www.facebook.com/doanhoikhoacnttvaa",
    "https://www.facebook.com/doanhoiftas",
    "https://www.facebook.com/profile.php?id=61555378444748",
    "https://www.facebook.com/doankhoadientuvaa",
    "https://www.facebook.com/sv5t.hoisinhvien.vaa",
    "https://www.facebook.com/aviationbasketball",
    "https://www.facebook.com/vepc.vaa",
    "https://www.facebook.com/VAA.SocialWork",
    "https://www.facebook.com/TinhNguyenVAA",
    "https://www.facebook.com/FromUAVClub",
    "https://www.facebook.com/aviationmanagementclub",
    "https://www.facebook.com/vaaphotography",
    "https://www.facebook.com/KySuTreVAA",
    "https://www.facebook.com/profile.php?id=100063550779612",
    "https://www.facebook.com/vaa.ys2016"
]

KEYWORDS = ["đăng ký", "sự kiện", "tuyển", "link", "form", "mở đơn", "workshop", "minigame", "ctv", "cuộc thi", "hội thảo"]
VN_TZ = timezone(timedelta(hours=7))

def parse_netscape_cookies(raw_text):
    cookies = []
    if not raw_text:
        return cookies
    for line in raw_text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.strip().split("\t")
        if len(parts) >= 7:
            cookies.append({
                "domain": parts[0],
                "path": parts[2],
                "secure": parts[3].upper() == "TRUE",
                "expires": int(parts[4]) if parts[4].isdigit() else -1,
                "name": parts[5],
                "value": parts[6]
            })
    return cookies

def load_seen():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(seen_set):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f)

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[!] Thiếu TELEGRAM_TOKEN hoặc CHAT_ID trong Secrets!", flush=True)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": False}, timeout=15)

def run_scan():
    seen = load_seen()
    is_first = len(seen) == 0
    fb_cookies = parse_netscape_cookies(FB_COOKIES_RAW)
    now_vn = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        if fb_cookies:
            context.add_cookies(fb_cookies)
        page = context.new_page()

        for url in PAGE_URLS:
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                articles = page.locator('[role="article"]').all()[:3]
                page_title = page.title().replace(" | Facebook", "").strip()

                for art in articles:
                    text = art.inner_text().strip()
                    if not text:
                        continue
                    post_sig = f"{url}_{hash(text[:120])}"
                    if post_sig in seen:
                        continue
                    seen.add(post_sig)
                    if is_first:
                        continue
                    if any(kw in text.lower() for kw in KEYWORDS):
                        first_line = next((l.strip() for l in text.splitlines() if l.strip()), "Bài viết mới")[:150]
                        msg = (
                            f"📢 [THÔNG BÁO MỚI]\n"
                            f"📰 Tiêu đề: {first_line}\n"
                            f"📌 Tên nhóm đăng: {page_title}\n"
                            f"🕒 Thời gian quét: {now_vn}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🔗 Link trang: {url}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🤖 {BOT_NAME}"
                        )
                        send_telegram(msg)
                        print(f"[+] Đã báo tin từ {page_title}", flush=True)
            except Exception as e:
                print(f"[!] Lỗi quét {url}: {e}", flush=True)

        browser.close()
    save_seen(seen)
    
if __name__ == "__main__":
    run_scan()
