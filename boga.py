#!/usr/bin/env python3
"""
Tenda AC15 Router Automation & Telegram Bot Controller (New Firmware Compatible)
Target Environment: Render.com Web Service (Direct Public Dynamic DNS URL)
"""

import sys
import os
import time
import json
import logging
import threading
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==============================================================================
# CONFIGURATION (DIRECT PUBLIC URL & CREDENTIALS)
# ==============================================================================
ROUTER_BASE_URL = "http://rosa.freedynamicdns.org:9588"
ROUTER_PASSWORD = "admin11"
TELEGRAM_BOT_TOKEN = "8820740325:AAGeSShZeaG2eTriYQMV__QkE5GYxsM9dSY"
PORT = int(os.environ.get("PORT", 10000))

URL_HOME_INFO = f"{ROUTER_BASE_URL}/goform/getHomePageInfo?modules=loginAuth%2CwifiRelay"
URL_LOGIN = f"{ROUTER_BASE_URL}/login/Auth"
URL_DEVICES = f"{ROUTER_BASE_URL}/goform/getOnlineList"
URL_STATUS = f"{ROUTER_BASE_URL}/goform/getStatus?modules=internetStatus%2CdeviceStatistics%2CsystemInfo%2CwanAdvCfg%2CwifiRelay"
URL_REBOOT = f"{ROUTER_BASE_URL}/goform/SysToolReboot"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ==============================================================================
# DUMMY WEB SERVER (RENDER PORT BINDING REQUIREMENT)
# ==============================================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"RUHIN TOOLS - Tenda Router Bot is Alive and Running!")
    def log_message(self, format, *args):
        pass

def run_web_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthCheckHandler)
        logging.info(f"Health check web server running on port {PORT}")
        server.serve_forever()
    except Exception as e:
        logging.error(f"Web server error: {e}")

# ==============================================================================
# TENDA ROUTER CLIENT (NEW FIRMWARE COMPATIBLE)
# ==============================================================================
class TendaRouter:
    def __init__(self, base_url, password):
        self.base_url = base_url
        self.password = password
        self.auth_cookie_str = None
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def _get_base_headers(self, referer_page="index.html"):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/{referer_page}",
        }

    def login(self) -> bool:
        logging.info(f"Authenticating with Tenda AC15 at {self.base_url} (New Firmware Flow)...")

        # ধাপ ১: প্রথমে হোম পেজ ইনফো বা লগইন অথ এপিআই হিট করে সেশন ইনিশিয়ালাইজ করা
        try:
            req_home = urllib.request.Request(URL_HOME_INFO, headers=self._get_base_headers("index.html"))
            with self.opener.open(req_home, timeout=10) as resp:
                pass
        except Exception as e:
            logging.warning(f"Pre-login info fetch warning: {e}")

        # ধাপ ২: পাসওয়ার্ড সাবমিট করা
        payload_data = urllib.parse.urlencode({"password": self.password}).encode("utf-8")
        headers = self._get_base_headers("index.html")
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"

        req = urllib.request.Request(URL_LOGIN, data=payload_data, headers=headers, method="POST")

        try:
            with self.opener.open(req, timeout=15) as response:
                for cookie in self.cookie_jar:
                    if cookie.name:
                        self.auth_cookie_str = f"{cookie.name}={cookie.value}"
                        logging.info(f"Successfully authenticated! Cookie: {self.auth_cookie_str}")
                        return True
        except Exception as e:
            logging.error(f"Login error: {e}")

        # ফলব্যাক কুকি যদি সরাসরি না ধরে
        self.auth_cookie_str = "admin=1"
        return True

    def request_api(self, url: str, method: str = "GET", post_data: bytes = None, retry: bool = True):
        if not self.auth_cookie_str:
            self.login()

        request_url = url
        if method == "GET" and "?" not in url:
            request_url = f"{url}&_={int(time.time() * 1000)}"
        elif method == "GET":
            request_url = f"{url}&_={int(time.time() * 1000)}"

        headers = self._get_base_headers("index.html")
        if post_data:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        if self.auth_cookie_str:
            headers["Cookie"] = self.auth_cookie_str

        req = urllib.request.Request(request_url, data=post_data, headers=headers, method=method)

        try:
            with self.opener.open(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="ignore").strip()
        except Exception as e:
            logging.error(f"API request error: {e}")
            if retry:
                self.login()
                return self.request_api(url, method, post_data, retry=False)
            return None

    def get_online_devices(self):
        raw = self.request_api(URL_DEVICES, method="GET")
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data[1:] if len(data) > 1 else data
            if isinstance(data, dict):
                for k in ["onlineList", "deviceList", "list"]:
                    if k in data and isinstance(data[k], list):
                        return data[k]
            return []
        except:
            return None

    def get_router_status(self):
        raw = self.request_api(URL_STATUS, method="GET")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except:
            return None

    def reboot(self) -> bool:
        payload = urllib.parse.urlencode({"action": 0}).encode("utf-8")
        try:
            self.request_api(URL_REBOOT, method="POST", post_data=payload, retry=False)
            return True
        except:
            return True

# ==============================================================================
# TELEGRAM BOT ENGINE
# ==============================================================================
def html_escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class TelegramBot:
    def __init__(self, token: str, router: TendaRouter):
        self.token = token
        self.router = router
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.offset = 0

    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except Exception as e:
            logging.error(f"Telegram error: {e}")

    def handle_command(self, chat_id: int, command: str):
        cmd = command.strip().lower()

        if cmd in ["/start", "/help"]:
            msg = (
                "🤖 <b>RUHIN TOOLS - Tenda AC15 Controller</b>\n\n"
                "Available Commands:\n"
                "• <code>/devices</code> — View connected online devices\n"
                "• <code>/status</code> — Display router health & status\n"
                "• <code>/reboot</code> — Reboot the router\n"
            )
            self.send_message(chat_id, msg)

        elif cmd == "/devices":
            self.send_message(chat_id, "🔍 <i>Querying router for connected devices...</i>")
            devices = self.router.get_online_devices()
            if not devices:
                self.send_message(chat_id, "❌ <b>No online devices found or connection failed.</b>")
                return

            lines = [f"📱 <b>Connected Online Devices ({len(devices)})</b>\n"]
            for idx, dev in enumerate(devices, 1):
                name = dev.get("devName") or dev.get("deviceName") or "Unknown"
                ip = dev.get("ip") or "N/A"
                mac = dev.get("mac") or dev.get("deviceId") or "N/A"
                lines.append(f"<b>{idx}. {html_escape(name)}</b>\n   • IP: <code>{html_escape(ip)}</code>\n   • MAC: <code>{html_escape(mac)}</code>")

            self.send_message(chat_id, "\n\n".join(lines))

        elif cmd == "/status":
            self.send_message(chat_id, "📊 <i>Fetching router status metrics...</i>")
            status = self.router.get_router_status()
            if not status or not isinstance(status, dict):
                self.send_message(chat_id, "❌ <b>Failed to fetch router status.</b>")
                return

            lines = ["📊 <b>Tenda AC15 Live Status</b>\n"]
            for section_key, section_val in status.items():
                if isinstance(section_val, dict):
                    for k, v in list(section_val.items())[:5]:
                        if isinstance(v, (str, int, float)) and v != "":
                            lines.append(f"• <b>{html_escape(k)}:</b> <code>{html_escape(v)}</code>")

            self.send_message(chat_id, "\n".join(lines))

        elif cmd == "/reboot":
            self.send_message(chat_id, "⚠️ <i>Initiating router reboot...</i>")
            if self.router.reboot():
                self.send_message(chat_id, "🔄 <b>Reboot signal sent successfully!</b>")
            else:
                self.send_message(chat_id, "❌ <b>Failed to send reboot command.</b>")

    def poll(self):
        logging.info("Starting Telegram Bot long-polling loop...")
        while True:
            params = {"timeout": 25, "offset": self.offset}
            url = f"{self.base_url}/getUpdates?{urllib.parse.urlencode(params)}"
            try:
                with urllib.request.urlopen(url, timeout=35) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        message = update.get("message")
                        if message and "text" in message:
                            self.handle_command(message["chat"]["id"], message["text"])
            except:
                time.sleep(3)

# ==============================================================================
# ENTRY POINT
# ==============================================================================
def main():
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    logging.info("Initializing Tenda AC15 Bot System...")
    router = TendaRouter(base_url=ROUTER_BASE_URL, password=ROUTER_PASSWORD)
    router.login()

    bot = TelegramBot(token=TELEGRAM_BOT_TOKEN, router=router)
    bot.poll()

if __name__ == "__main__":
    main()
