import time
import json
import os
import threading
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask

# ================= CẤU HÌNH CỦA BẠN =================
TELEGRAM_TOKEN = "9053069383:AAHLYyltFj0TnGYosJ7pjUWtVrXthDf_i0Q"
CHAT_ID = "9012032761"
APIFY_TOKEN = "apify_api_SylBsl3wPQZsbZ0MJxbrhZkzFhyPEh1wsHr2"  # Dán mã apify_api_... của bạn vào đây
BOT_NAME = "Yuki 2 (VAA)"

# Danh sách 29 Fanpage cần theo dõi
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

# Từ khóa lọc bài sự kiện (Để trống [] nếu muốn nhận TẤT CẢ bài đăng mới từ 29 page)
KEYWORDS = ["đăng ký", "sự kiện", "tuyển", "link", "form", "mở đơn", "workshop", "minigame", "ctv", "cuộc thi", "hội thảo"]

SCAN_INTERVAL_SECONDS = 1200  # Quét 20 phút/lần để tiết kiệm tối đa gói $5 miễn phí cả tháng
MAX_POST_AGE_MINUTES = 180    # Chỉ báo bài đăng trong vòng 3 tiếng gần nhất
HISTORY_FILE = "seen_apify_posts.json"
# ======================================================

app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 {BOT_NAME} (Apify Cloud Mode) đang theo dõi {len(PAGE_URLS)} Fanpage 24/7!"

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

def fetch_posts_via_apify():
    """Gọi Apify lấy bài viết mới nhất từ danh sách 29 Fanpage"""
    api_url = f"https://api.apify.com/v2/acts/apify~facebook-posts-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    payload = {
        "startUrls": [{"url": u} for u in PAGE_URLS],
        "resultsLimit": 1,  # Lấy 1 bài mới nhất mỗi page để tối ưu gói miễn phí
        "onlyPostsNewerThan": "3 hours"
    }
    res = requests.post(api_url, json=payload, timeout=180)
    if res.status_code in [200, 201]:
        return res.json()
    else:
        print(f"[!] Lỗi từ Apify ({res.status_code}): {res.text[:200]}", flush=True)
        return []

def monitor():
    seen_posts = load_seen_posts()
    print(f"🚀 {BOT_NAME} (Apify Mode) đã khởi động!", flush=True)
    send_telegram(f"🤖 {BOT_NAME} đã kết nối Apify thành công và bắt đầu quét {len(PAGE_URLS)} Fanpage!")

    while True:
        now_vn = datetime.now(VN_TZ)
        # Chỉ quét trong khung giờ 07:00 - 23:00 để tiết kiệm credit miễn phí ban đêm
        if 7 <= now_vn.hour <= 23:
            if APIFY_TOKEN.startswith("NHẬP_"):
                print("⚠️ Bạn chưa điền APIFY_TOKEN!", flush=True)
            else:
                try:
                    print(f"🔎 [{now_vn.strftime('%H:%M:%S')}] Đang quét 29 Fanpage qua Apify...", flush=True)
                    items = fetch_posts_via_apify()
                    print(f"✅ Apify trả về {len(items)} bài mới trong 3 giờ qua.", flush=True)

                    for item in items:
                        post_url = item.get("url") or item.get("postUrl") or ""
                        post_id = item.get("postId") or post_url
                        if not post_id or post_id in seen_posts:
                            continue

                        seen_posts.add(post_id)
                        save_seen_posts(seen_posts)

                        text = item.get("text") or item.get("message") or ""
                        if not check_keywords(text):
                            continue

                        title = extract_title(text)
                        page_name = item.get("pageName") or item.get("user", {}).get("name") or "Fanpage VAA"
                        
                        raw_time = item.get("time")
                        if raw_time:
                            try:
                                dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).astimezone(VN_TZ)
                                post_time = dt.strftime("%d/%m/%Y %H:%M:%S")
                            except Exception:
                                post_time = now_vn.strftime("%d/%m/%Y %H:%M:%S")
                        else:
                            post_time = now_vn.strftime("%d/%m/%Y %H:%M:%S")

                        msg = format_message(title, page_name, post_time, post_url)
                        send_telegram(msg)
                        print(f"[+] Đã gửi thông báo mới từ {page_name}: {title}", flush=True)

                except Exception as e:
                    print(f"[!] Lỗi hệ thống khi quét: {e}", flush=True)
        else:
            print(f"💤 Ngoài khung giờ 7h-23h ({now_vn.strftime('%H:%M')}), tạm nghỉ tiết kiệm gói miễn phí...", flush=True)

        time.sleep(SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    monitor()
