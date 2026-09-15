import os
import re
import base64
import time
import urllib.parse
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# تنظیم دقیق تگ با یک عدد @
env_tag = os.getenv("CHANNEL_TAG")
if not env_tag or env_tag.strip().lower() in ["none", "null", ""]:
    CHANNEL_TAG = "👉🆔@Goodbaye_filtering📡"
else:
    CHANNEL_TAG = env_tag.strip()

# جلوگیری هوشمند از ایجاد دو عدد @@ پشت سر هم
CHANNEL_TAG = re.sub(r'@+', '@', CHANNEL_TAG)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def decode_base64_safely(data: str) -> str:
    clean_data = data.strip().replace("\r", "").replace("\n", "")
    missing_padding = len(clean_data) % 4
    if missing_padding:
        clean_data += "=" * (4 - missing_padding)
    try:
        decoded_bytes = base64.b64decode(clean_data)
        return decoded_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def clean_old_remark(old_tag: str) -> str:
    """حذف آیدی‌ها، سایت‌ها، تبلیغات متفرقه و نگه‌داشتن پرچم، نام کشور و پینگ"""
    if not old_tag or old_tag.lower() in ["none", "null", ""]:
        return ""
    
    t = old_tag

    # ۱. حذف آدرس وب‌سایت‌ها و دامنه‌ها (مثل [openproxylist.com] یا site.ir)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'(?:https?:\/\/)?t\.me\/[\w\d_\.-]+', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\[?[\w\d_\.-]+\.(?:com|net|org|ir|io|me|info|site|xyz|life|app|ru|co|top)\]?', '', t, flags=re.IGNORECASE)

    # ۲. حذف الگوهای آیدی تلگرام مثل 👉🆔@channel📡 یا @channel
    t = re.sub(r'👉\s*🆔\s*@+[\w\d_\.-]+\s*📡?', '', t)
    t = re.sub(r'@+[\w\d_\.-]+', '', t)

    # ۳. حذف نوشته‌های نام پروتکل اضافی مثل vless-US یا vmess-DE
    t = re.sub(r'\b(?:vless|vmess|trojan|ss|ssr|hysteria\d?)[-_ ]*[a-zA-Z0-9]*\b', '', t, flags=re.IGNORECASE)

    # ۴. پاک‌سازی براکت‌های خالی باقی‌مانده [] ()
    t = re.sub(r'[\[\]\(\)\{\}]', ' ', t)

    # ۵. پاک‌سازی خط فاصله و کاراکترهای اضافه از ابتدا و انتهای متن
    t = re.sub(r'^[|\-—_:,\s]+', '', t).strip()
    t = re.sub(r'[|\-—_:,\s]+$', '', t).strip()
    return t

def fetch_source_configs(url: str) -> list:
    configs = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"[SKIP] Status code {response.status_code} for URL: {url}")
            return configs

        content = response.text.strip()
        if not content:
            return configs

        if not content.startswith("vless://"):
            decoded = decode_base64_safely(content)
            if "vless://" in decoded:
                content = decoded

        for line in content.splitlines():
            line = line.strip()
            if line.startswith("vless://"):
                configs.append(line)

    except requests.exceptions.Timeout:
        print(f"[TIMEOUT] Skipping slow source: {url}")
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Error connecting to {url}: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error parsing {url}: {e}")

    return configs

def filter_and_deduplicate(raw_configs: list) -> list:
    unique_fingerprints = set()
    filtered_list = []

    for cfg in raw_configs:
        try:
            parts = cfg.split("#", 1)
            clean_url = parts[0].strip()

            # پاک‌سازی اطلاعات قبلی و نگه‌داشتن کشور و پینگ
            old_tag = ""
            if len(parts) > 1:
                decoded_old = urllib.parse.unquote(parts[1]).strip()
                old_tag = clean_old_remark(decoded_old)

            parsed = urllib.parse.urlparse(clean_url)
            queries = urllib.parse.parse_qs(parsed.query)

            security = queries.get("security", [""])[0].lower()
            transport_type = queries.get("type", [""])[0].lower()
            flow = queries.get("flow", [""])[0].lower()

            is_grpc = (transport_type == "grpc")
            is_vision = ("xtls-rprx-vision" in flow)

            if security == "reality" and (is_grpc or is_vision):
                server_host = parsed.hostname or ""
                server_port = parsed.port or ""
                sni = queries.get("sni", [""])[0].lower()
                pbk = queries.get("pbk", [""])[0]

                unique_key = f"{server_host}:{server_port}-{sni}-{pbk}-{transport_type}-{flow}"

                if unique_key not in unique_fingerprints:
                    unique_fingerprints.add(unique_key)
                    
                    if old_tag:
                        final_tag_text = f"{CHANNEL_TAG}{old_tag}"
                    else:
                        final_tag_text = f"{CHANNEL_TAG}⚡️"

                    encoded_tag = urllib.parse.quote(final_tag_text)
                    final_config = f"{clean_url}#{encoded_tag}"
                    filtered_list.append(final_config)
        except Exception:
            continue

    return filtered_list

def send_file_only_to_telegram(configs: list):
    if not BOT_TOKEN or not CHAT_ID:
        print("[WARN] Telegram BOT_TOKEN or CHAT_ID is missing.")
        return

    if not configs:
        print("[INFO] No matching Reality configs found.")
        return

    file_name = "Reality_VIP_Configs.txt"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write("\n".join(configs))

    caption = (
        f"📁 <b>فایل اختصاصی کانفیگ‌های Reality (gRPC & Vision)</b>\n\n"
        f"⚡️ <b>تعداد کل کانفیگ‌ها:</b> {len(configs)} عدد\n"
        f"🛡 <b>پروتکل‌ها:</b> Reality gRPC و Reality TCP-Vision\n"
        f"🔄 <b>بروزرسانی خودکار:</b> هر ۴ ساعت یکبار\n\n"
        f"📥 <i>این فایل را در نرم‌افزارهای V2rayNG یا NekoBox ایمپورت کنید.</i>\n\n"
        f"📢 {CHANNEL_TAG}\n"
        f"➖➖➖➖➖➖➖➖➖➖"
    )

    doc_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(file_name, "rb") as doc:
            requests.post(
                doc_url,
                data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"document": (file_name, doc, "text/plain")},
                timeout=30
            )
        print("[OK] Cleaned VIP file sent successfully to Telegram.")
    except Exception as e:
        print(f"[FAIL] Sending document failed: {e}")

def main():
    if not os.path.exists("sources.txt"):
        print("sources.txt not found!")
        return

    with open("sources.txt", "r", encoding="utf-8") as f:
        sources = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    all_raw_configs = []
    for idx, url in enumerate(sources, 1):
        print(f"[{idx}/{len(sources)}] Fetching from: {url}")
        configs = fetch_source_configs(url)
        all_raw_configs.extend(configs)

    final_configs = filter_and_deduplicate(all_raw_configs)
    print(f"Total Unique Cleaned Reality configs: {len(final_configs)}")

    send_file_only_to_telegram(final_configs)

if __name__ == "__main__":
    main()
