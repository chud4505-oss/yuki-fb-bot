import time
import json
import os
import re
import threading
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask
from facebook_scraper import get_posts

# ================= CẤU HÌNH CỦA BẠN =================
TELEGRAM_TOKEN = "9053069383:AAHLYyltFj0TnGYosJ7pjUWtVrXthDf_i0Q"
CHAT_ID = "9012032761"
BOT_NAME = "Yuki 2 (VAA)"

# Danh sách 28 Fanpage cần theo dõi (Bao gồm username, ID số và link /share/)
RAW_PAGES = [
    # 1. Trung tâm nghiên cứu và phát triển số
    "https://www.facebook.com/share/1dgGyoXTVj/",
    # 2. Đoàn hội khoa kỹ thuật hàng không
    "https://www.facebook.com/share/1CNVF6gczy/",
    # 3. Đoàn hội khoa khai thác hàng không
    "https://www.facebook.com/share/1E2FRrGoRm/",
    # 4. Đoàn hội khoa quản trị kinh doanh
    "https://www.facebook.com/share/18wH6FkSkm/",
    # 5. VAA Global-Citizen Students Club - GLOCIS
    "https://www.facebook.com/share/1Eo824EEth/",
    # 6. Đoàn hội khoa kinh tế hàng không
    "https://www.facebook.com/share/1EUgstua62/",
    # 7. Đoàn thanh niên - Hội sinh viên
    "DoanTNHoiSV.VAU",
    # 8. Khoa du lịch và dịch vụ hàng không
    "ftas.vaa.vn",
    # 9. Khoa ngoại ngữ
    "khoangoainguVAA",
    # 10. CLB Lý luận trẻ
    "clblyluantrevaa",
    # 11. CLB Logistic
    "100092618240008",
    # 12. CLB English
    "3e.vaaec",
    # 13. CLB Bóng chuyền
    "VolleyballClub.VAA",
    # 14. Đoàn hội khoa CNTT
    "doanhoikhoacnttvaa",
    # 15. Đoàn hội khoa Du lịch
    "doanhoiftas",
    # 16. Đoàn hội khoa Xây dựng
    "61555378444748",
    # 17. Đoàn hội khoa Điện
    "doankhoadientuvaa",
    # 18. CLB Sinh viên 5 tốt
    "sv5t.hoisinhvien.vaa",
    # 19. CLB Bóng rổ
    "aviationbasketball",
    # 20. CLB Tổ chức sự kiện
    "vepc.vaa",
    # 21. Đội CTXH
    "VAA.SocialWork",
    # 22. Tình nguyện
    "TinhNguyenVAA",
    # 23. CLB UAV
    "FromUAVClub",
    # 24. CLB AMC
    "aviationmanagementclub",
    # 25. CLB Nhiếp ảnh
    "vaaphotography",
    # 26. CLB Kỹ sư trẻ
    "KySuTreVAA",
    # 27. Công tác sinh viên
    "100063550779612",
    # 28. CLB Khoa học trẻ
    "https://www.facebook.com/share/1D5zobMuVA/"
]

# Từ khóa lọc bài sự kiện (Để trống [] nếu muốn nhận TẤT CẢ bài đăng mới từ 28 page)
KEYWORDS = ["đăng ký", "sự kiện", "tuyển", "link", "form", "mở đơn", "workshop", "minigame", "ctv", "cuộc thi", "hội thảo"]

CHECK_INTERVAL = 60  # Nghỉ 60 giây sau khi quét xong 1 vòng 28 page
HISTORY_FILE = "seen_posts.json"
COOKIES_FILE = "cookies.txt"
# ======================================================

app = Flask(__name__)

@app.route('/')
def home():
    return f"🤖 {BOT_NAME} đang theo dõi {len(RAW_PAGES)} Fanpage 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

VN_TZ = timezone(timedelta(hours=7))

def resolve_page_identifier(item):
    """Tự động giải mã các link facebook.com/share/... thành username hoặc ID gốc"""
    if not item.startswith("http"):
        return item
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        res = requests.get(item, headers=headers, allow_redirects=True, timeout=10)
        final_url = res.url
        
        # Trường hợp chuyển hướng về profile.php?id=123456
        id_match = re.search(r"id=(\d+)", final_url)
        if id_match:
            return id_match.group(1)
            
        # Trường hợp chuyển hướng về facebook.com/username
        user_match = re.search(r"facebook\.com/([^/?#]+)", final_url)
        if user_match and user_match.group(1) not in ["share", "login", "profile.php"]:
            return user_match.group(1)
    except Exception as e:
        print(f"[!] Không giải mã được link {item}: {e}")
    return None

def build_page_list():
    resolved = []
    print("🔄 Đang chuẩn hóa danh sách 28 Fanpage...")
    for item in RAW_PAGES:
        clean_id = resolve_page_identifier(item)
        if clean_id:
            resolved.append(clean_id)
            if item.startswith("http"):
                print(f"   ✓ Đã giải mã: {item} -> {clean_id}")
        else:
            print(f"   ✗ Bỏ qua link lỗi: {item}")
    return resolved

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
            print(f"[Lỗi Telegram API]: {res.text}")
    except Exception as e:
        print(f"[Lỗi kết nối Telegram]: {e}")

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
    pages_to_scan = build_page_list()
    
    print(f"🚀 {BOT_NAME} đã sẵn sàng! Bắt đầu quét {len(pages_to_scan)} Fanpage...")
    if not cookies:
        print("⚠️ Cảnh báo: Bắt buộc nên có cookies.txt khi quét 28 page để tránh bị FB chặn!")

    # Lần chạy đầu tiên: Đánh dấu các bài cũ đã có sẵn để tránh spam 50 tin nhắn cùng lúc
    is_first_run = len(seen_posts) == 0
    if is_first_run:
        print("⏳ Lần chạy đầu tiên: Đang đồng bộ các bài viết cũ để tránh spam...")

    while True:
        for page in pages_to_scan:
            try:
                posts = get_posts(
                    page,
                    pages=1,
                    cookies=cookies,
                    options={"posts_per_page": 2}
                )
                
                for post in posts:
                    post_id = post.get("post_id")
                    if not post_id or post_id in seen_posts:
                        continue
                    
                    seen_posts.add(post_id)
                    save_seen_posts(seen_posts)
                    
                    # Nếu là lần đồng bộ đầu tiên thì chỉ lưu ID, không gửi thông báo
                    if is_first_run:
                        continue
                        
                    text = post.get("text", "") or ""
                    if not check_keywords(text):
                        continue
                    
                    title = extract_title(text)
                    page_name = post.get("username") or page
                    
                    raw_time = post.get("time")
                    if isinstance(raw_time, datetime):
                        post_time = raw_time.strftime("%d/%m/%Y %H:%M:%S")
                    else:
                        post_time = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
                        
                    post_url = post.get("post_url") or f"https://www.facebook.com/{page}/posts/{post_id}"
                    
                    msg = format_message(title, page_name, post_time, post_url)
                    send_telegram(msg)
                    print(f"[+] Đã gửi thông báo mới từ {page_name}: {title}")
                    
            except Exception as e:
                print(f"[!] Lỗi khi quét '{page}': {e}")
            
            # Nghỉ 3.5 giây giữa mỗi page để an toàn cho tài khoản cookies
            time.sleep(3.5)
            
        if is_first_run:
            is_first_run = False
            print("✅ Đã đồng bộ xong bài cũ! Từ giờ hễ có bài mới là bot sẽ báo ngay.")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    monitor()
