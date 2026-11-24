import time
import json
import os
import threading
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask
from facebook_scraper import get_posts

# ================= CẤU HÌNH CỦA BẠN =================
TELEGRAM_TOKEN = "9053069383:AAHLYyltFj0TnGYosJ7pjUWtVrXthDf_i0Q"
CHAT_ID = "9012032761"
BOT_NAME = "Yuki 2 (VAA)"

PAGES = [
    "drd.vau",
    "doanhoi.khoangoaingu.vaa",
    "doanhoikhoakythuathangkhong",
    "doanhoikhoakhaithachangkhong",
    "vaa.doanhoikhoaquantrikinhdoanh",
    "61576624683756",
    "doanhoi.kinhtehangkhong.vaa",
    "DoanTNHoiSV.VAU",
    "ftas.vaa.vn",
    "khoangoainguVAA",
    "clblyluantrevaa",
    "100092618240008",
    "3e.vaaec",
    "VolleyballClub.VAA",
    "doanhoikhoacnttvaa",
    "doanhoiftas",
    "61555378444748",
    "doankhoadientuvaa",
    "sv5t.hoisinhvien.vaa",
    "aviationbasketball",
    "vepc.vaa",
    "VAA.SocialWork",
    "TinhNguyenVAA",
    "FromUAVClub",
    "aviationmanagementclub",
    "vaaphotography",
    "KySuTreVAA",
    "100063550779612",
    "vaa.ys2016"
]

KEYWORDS = ["đăng ký", "sự kiện", "tuyển", "link", "form", "mở đơn", "workshop", "minigame", "ctv", "cuộc thi", "hội thảo"]

CHECK_INTERVAL = 45
MAX_POST_AGE_MINUTES = 180
HISTORY_FILE = "seen_posts.json"
COOKIES_FILE = "cookies.txt"
# ======================================================

app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 {BOT_NAME} đang theo dõi {len(PAGES)} Fanpage 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

VN_TZ = timezone(timedelta(hours=7))

def load_seen_posts():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_posts(seen_set):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": False
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code != 200:
            print(f"[Lỗi Telegram API]: {res.text}", flush=True)
    except Exception as e:
        print(f"[Lỗi kết nối Telegram]: {e}", flush=True)

def check_keywords(text):
    if not KEYWORDS:
        return True
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)

def extract_title(text):
    if not text:
        return "Bài viết mới (Không có nội dung văn bản)"
    for line in text.splitlines():
        clean_line = line.strip()
        if clean_line:
            return clean_line[:150] + ("..." if len(clean_line) > 150 else "")
    return "Bài viết mới"

def format_message(title, page_name, post_time, post_url):
    return (
        f"📢 [THÔNG BÁO MỚI]\n"
        f"📰 Tiêu đề: {title}\n"
        f"📌 Tên nhóm đăng: {page_name}\n"
        f"🕒 Thời gian đăng: {post_time}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 Link bài viết: {post_url}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!\n"
        f"🤖 {BOT_NAME}"
    )

def monitor():
    seen_posts = load_seen_posts()
    cookies = COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
    
    print(f"🚀 {BOT_NAME} đã sẵn sàng! Cookies: {'Có' if cookies else 'Không'}", flush=True)
    send_telegram(f"🤖 {BOT_NAME} đã khởi động chế độ kiểm tra chi tiết!")

    while True:
        now_utc = datetime.now(timezone.utc)
        
        for page in PAGES:
            try:
                posts = list(get_posts(
                    page,
                    pages=1,
                    cookies=cookies,
                    options={"posts_per_page": 4}
                ))
                print(f"🔎 Quét '{page}': tìm thấy {len(posts)} bài", flush=True)
                
                for post in posts:
                    post_id = post.get("post_id")
                    if not post_id or post_id in seen_posts:
                        continue
                    
                    seen_posts.add(post_id)
                    save_seen_posts(seen_posts)
                    
                    raw_time = post.get("time")
                    if isinstance(raw_time, datetime):
                        post_utc = raw_time.replace(tzinfo=timezone.utc) if raw_time.tzinfo is None else raw_time
                        age_minutes = (now_utc - post_utc).total_seconds() / 60
                        if age_minutes > MAX_POST_AGE_MINUTES:
                            continue
                        post_time = post_utc.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
                    else:
                        post_time = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
                        
                    text = post.get("text", "") or ""
                    if not check_keywords(text):
                        continue
                    
                    title = extract_title(text)
                    page_name = post.get("username") or page
                    post_url = post.get("post_url") or f"https://www.facebook.com/{page}/posts/{post_id}"
                    
                    msg = format_message(title, page_name, post_time, post_url)
                    send_telegram(msg)
                    print(f"[+] Đã gửi thông báo mới từ {page_name}: {title}", flush=True)
                    
            except Exception as e:
                print(f"[!] Lỗi khi quét '{page}': {e}", flush=True)
            
            time.sleep(3)
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    monitor()
