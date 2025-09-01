# utils.py
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import json
import threading
import time
from pathlib import Path

# ---------- Lightweight config loader (.env + config.json) ----------
def _company_dir_early() -> Path:
    appdata_path = os.environ.get('APPDATA')
    return Path(appdata_path) / "BokkChoYCompany" if appdata_path else Path.cwd()


def _read_env_file(path: Path) -> dict:
    data: dict[str, str] = {}
    try:
        if not path.exists():
            return data
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if '=' not in s:
                continue
            k, v = s.split('=', 1)
            data[k].strip() if False else None  # keep type checker quiet
            data[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return data


def _load_env_from_files() -> None:
    # Load from .env in CWD then AppData folder, without overriding existing env
    for p in [Path.cwd() / ".env", _company_dir_early() / ".env"]:
        try:
            envmap = _read_env_file(p)
            for k, v in envmap.items():
                if k and (os.getenv(k) is None):
                    os.environ[k] = v
        except Exception:
            pass


def _load_config_overrides() -> dict:
    # Optional JSON config in AppData: {"API_TOKEN": "...", "SPREADSHEET_KEY": "..."}
    try:
        cfg_path = _company_dir_early() / "config.json"
        if cfg_path.exists():
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


_load_env_from_files()
_CONFIG_OVERRIDES = _load_config_overrides()

# Constants (sanitized: read from env, no hardcoded secrets)
def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    if v is not None and v != "":
        return v
    if name in _CONFIG_OVERRIDES and str(_CONFIG_OVERRIDES[name]).strip():
        return str(_CONFIG_OVERRIDES[name]).strip()
    return default

API_KEYS = {
    "branchs": _env("API_KEY_BRANCHS"),
    "pmrocket": _env("API_KEY_PMROCKET"),
    "rocketbooking": _env("API_KEY_ROCKETBOOKING"),
    "times": _env("API_KEY_TIMES"),
    "ithitec": _env("API_KEY_ITHITEC"),
    "token": _env("API_TOKEN"),
}
BASE_URL = _env("CREDENTIALS_BASE_URL", "https://backend-secure-cred-api.onrender.com/get-credentials")

# โหลด Google API credentials.json จาก backend
def get_google_credentials_json():
    token = (API_KEYS.get("token") or "").strip()
    if not token:
        raise RuntimeError("Missing API_TOKEN environment variable")
    headers = {"X-API-Token": token}
    response = requests.get(BASE_URL, headers=headers)
    response.raise_for_status()
    return response.json()

# สร้าง gspread client
def create_gsheet_client():
    creds_json = get_google_credentials_json()
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scope)
    client = gspread.authorize(creds)
    return client

# ฟังก์ชันเปิด Google Sheet ด้วย spreadsheet key
def open_google_sheet(client, sheet_key):
    return client.open_by_key(sheet_key)

# โหลด API data ทั้งหมดพร้อมกัน
def fetch_api(api_key):
    headers = {"X-API-Token": api_key}
    try:
        response = requests.get(BASE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return f"Error: {e}"

def get_all_api_data():
    results = {}
    for name, key in API_KEYS.items():
        results[name] = fetch_api(key)
    return results

# ---------- Today Booking helpers ----------
def is_today_booking_open(sheet_name: str = "todaybooking",
                          date_column: str = "Date",
                          flag_column: str = "Booking Day") -> bool:
    """
    ตรวจสอบจากชีต todaybooking ว่าวันนี้เปิดจองหรือไม่
    - sheet_name: ชื่อแท็บ เช่น todaybooking
    - date_column: ชื่อหัวคอลัมน์วันที่ เช่น Date
    - flag_column: ชื่อหัวคอลัมน์สถานะ เช่น Booking Day
    เงื่อนไข: หาแถวที่ตรงกับวันที่วันนี้ และ flag เป็น TRUE/true/1/Yes
    """
    client = create_gsheet_client()
    if not SPREADSHEET_KEY:
        raise RuntimeError("Missing SPREADSHEET_KEY environment variable")
    ws = open_google_sheet(client, SPREADSHEET_KEY).worksheet(sheet_name)
    records = ws.get_all_records()
    today = datetime.now().date()
    def parse_date(val):
        if not val:
            return None
        s = str(val).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        return None
    def truthy(val):
        s = str(val).strip().lower()
        return s in ("true", "1", "yes", "y")
    for row in records:
        d = parse_date(row.get(date_column))
        if d == today:
            return truthy(row.get(flag_column))
    return False

# ส่วนที่เพิ่มเข้ามาสำหรับการจัดการ Google Sheet Login
SPREADSHEET_KEY = _env("SPREADSHEET_KEY")
SHEET_NAME = "Users" # เปลี่ยนตามชื่อ sheet จริง
TOPUP_SHEET_NAME = "Topups"

def google_sheet_check_login(username, password):
    try:
        client = create_gsheet_client()
        if not SPREADSHEET_KEY:
            raise RuntimeError("Missing SPREADSHEET_KEY environment variable")
        sheet = open_google_sheet(client, SPREADSHEET_KEY).worksheet(SHEET_NAME)
        records = sheet.get_all_records()
        user = None
        u_in = str(username).strip()
        p_in = str(password).strip()
        for row in records:
            # ทำให้ปลอดภัยต่อค่าที่เป็นตัวเลข/ชนิดอื่น ๆ จากชีต
            name = str(row.get("Username", "")).strip()
            pw = str(row.get("Password", "")).strip()
            if name == u_in and pw == p_in:
                user = row
                break

        if user is None:
            return None

        # เช็ควันหมดอายุ (format yyyy-mm-dd) แบบเทียบรายวัน
        exp_raw = user.get("Expiration date", "")
        if exp_raw is not None and exp_raw != "":
            try:
                if isinstance(exp_raw, datetime):
                    exp_d = exp_raw.date()
                else:
                    s = str(exp_raw).strip()
                    parsed = None
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            parsed = datetime.strptime(s, fmt).date()
                            break
                        except Exception:
                            continue
                    exp_d = parsed
                if exp_d and exp_d < datetime.now().date():
                    return "expired"  # วันหมดอายุเก่ากว่าวันนี้
            except Exception:
                # หาก parse ไม่ได้ ให้ถือว่าไม่หมดอายุ
                pass
        return user
    except Exception as e:
        raise Exception(f"Failed to connect to Google Sheet or check login: {e}")

def setup_config_files():
    """
    ตรวจสอบและสร้างโฟลเดอร์ BokkChoYCompany และไฟล์ config ที่จำเป็น
    ถ้ายังไม่มีอยู่
    """
    appdata_path = os.environ.get('APPDATA')
    if not appdata_path:
        print("ไม่พบ AppData path. ไม่สามารถสร้าง config ได้")
        return

    company_dir = Path(appdata_path) / "BokkChoYCompany"
    
    if not company_dir.exists():
        print(f"กำลังสร้างโฟลเดอร์: {company_dir}")
        os.makedirs(company_dir)
    
    # สร้างไฟล์พื้นฐานที่ต้องใช้
    files_to_check = {
        # ใส่ template ค่าเริ่มต้น (รูปแบบ list ของออบเจ็กต์ id/Email/Password)
        "line_data.json": [
            {"id": 1, "Email": "", "Password": ""}
        ],
        "scheduled_tasks.json": [],
        # โปรไฟล์เดี่ยว (เดิม) คงไว้เพื่อรองรับย้อนหลัง
        "user_profile.json": {
            # "Firstname": "",
            # "Lastname": "",
            # "Gender": "",  # ชื่อที่กดใน ant-select เช่น "Mr." หรือเว้นว่าง
            # "ID": "",
            # "Phone": ""
        },
        # โปรไฟล์หลายคน (ใหม่)
        "user_profiles.json": [
            {
                "id": 1,
                "Name": "Default",
                "Firstname": "",
                "Lastname": "",
                "Gender": "",
                "ID": "",
                "Phone": ""
            }
        ]
    }
    
    for filename, default_content in files_to_check.items():
        file_path = company_dir / filename
        if not file_path.exists():
            print(f"กำลังสร้างไฟล์: {file_path}")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_content, f, indent=4, ensure_ascii=False)

    # Migration: แปลง user_profile.json (เดิม) เป็น user_profiles.json (ใหม่) หากยังไม่มีไฟล์ใหม่
    try:
        legacy = company_dir / "user_profile.json"
        multi = company_dir / "user_profiles.json"
        if legacy.exists() and not multi.exists():
            with open(legacy, 'r', encoding='utf-8') as f:
                one = json.load(f) or {}
            default_profile = {
                "id": 1,
                "Name": "Default",
                "Firstname": one.get("Firstname", ""),
                "Lastname": one.get("Lastname", ""),
                "Gender": one.get("Gender", ""),
                "ID": one.get("ID", ""),
                "Phone": one.get("Phone", "")
            }
            with open(multi, 'w', encoding='utf-8') as f:
                json.dump([default_profile], f, indent=4, ensure_ascii=False)
    except Exception:
        pass

    print("ตั้งค่าไฟล์ config สำเร็จ")


def register_user(username: str,
                  password: str,
                  role: str = "normal",
                  max_sites: int = 1,
                  can_schedule: str = "ไม่",
                  expiration_date: str | None = None) -> dict:
    """
    ลงทะเบียนผู้ใช้ใหม่ลงชีต Users ด้วยค่าเริ่มต้นที่กำหนด
    - ถ้า username ซ้ำ จะยกข้อยกเว้น
    - expiration_date: ถ้าไม่ระบุ จะใช้วันที่วันนี้ (YYYY-MM-DD)
    คืนค่า row ที่เพิ่ม (dict) เมื่อสำเร็จ
    """
    try:
        if not username or not password:
            raise ValueError("Username/Password ห้ามว่าง")
        expiration_date = expiration_date or datetime.now().strftime("%Y-%m-%d")
        client = create_gsheet_client()
        ws = open_google_sheet(client, SPREADSHEET_KEY).worksheet(SHEET_NAME)
        records = ws.get_all_records()
        for row in records:
            if str(row.get("Username", "")).strip() == str(username).strip():
                raise ValueError("Username นี้ถูกใช้งานแล้ว")
        # จัด map header -> index
        headers = ws.row_values(1)
        header_index = {h: i for i, h in enumerate(headers)}
        # เตรียมแถวใหม่ตาม header เดิมของชีต
        new_row = [""] * max(len(headers), 6)
        def set_col(name: str, value: str):
            if name in header_index:
                idx = header_index[name]
                if idx >= len(new_row):
                    new_row.extend([""] * (idx - len(new_row) + 1))
                new_row[idx] = value
        set_col("Username", str(username).strip())
        set_col("Password", str(password).strip())
        set_col("Role", str(role).strip())
        set_col("สามาถตั้งจองล่วงหน้าได้กี่ site", str(max_sites))
        set_col("ตั้งจองล่วงหน้าได้ไหม", str(can_schedule))
        set_col("Expiration date", str(expiration_date))
        # เติมค่า channels ที่ชีตอาจมีหัวคอลัมน์มากกว่าที่เราเซ็ตไว้ด้วยค่าว่างตามเดิม
        if not new_row:
            new_row = [str(username), str(password), str(role), str(max_sites), str(can_schedule), str(expiration_date)]
        ws.append_row(new_row)
        return {
            "Username": username,
            "Password": password,
            "Role": role,
            "สามาถตั้งจองล่วงหน้าได้กี่ site": max_sites,
            "ตั้งจองล่วงหน้าได้ไหม": can_schedule,
            "Expiration date": expiration_date
        }
    except Exception as e:
        raise Exception(f"Failed to register user: {e}")


# ---------- LINE credential helpers ----------
def _company_dir() -> Path:
    appdata_path = os.environ.get('APPDATA')
    return Path(appdata_path) / "BokkChoYCompany" if appdata_path else Path.cwd()


def load_line_credentials() -> dict:
    try:
        path = _company_dir() / "line_data.json"
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # รูปแบบใหม่ (list ของออบเจ็กต์)
        if isinstance(data, list):
            result = {}
            for item in data:
                if not isinstance(item, dict):
                    continue
                email = (item.get("Email") or item.get("email") or "").strip()
                password = (item.get("Password") or item.get("password") or "").strip()
                if email and password:
                    result[email] = password
            return result
        # รูปแบบเก่าแบบคู่ key Email/Password
        if isinstance(data, dict) and ("Email" in data or "email" in data) and ("Password" in data or "password" in data):
            email = data.get("Email") or data.get("email")
            password = data.get("Password") or data.get("password")
            if email and password:
                return {email: password}
            return {}
        # รูปแบบ dict {email: password}
        if isinstance(data, dict):
            # กรองคีย์ template ออก (คีย์ที่ขึ้นต้นด้วย "__")
            return {k: v for k, v in data.items() if not str(k).startswith("__")}
        return {}
    except Exception:
        return {}


def load_user_profile() -> dict:
    try:
        path = _company_dir() / "user_profile.json"
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

# ---------- Multi-user profile helpers ----------

def _profiles_path() -> Path:
    return _company_dir() / "user_profiles.json"


def load_user_profiles() -> list:
    """โหลดรายการโปรไฟล์ทั้งหมดจาก user_profiles.json ถ้าไม่พบให้พยายามสร้างจาก user_profile.json (เดิม)"""
    try:
        p_multi = _profiles_path()
        if p_multi.exists():
            with open(p_multi, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        # fallback/migrate from single profile
        one = load_user_profile() or {}
        return [{
            "id": 1,
            "Name": "Default",
            "Firstname": one.get("Firstname", ""),
            "Lastname": one.get("Lastname", ""),
            "Gender": one.get("Gender", ""),
            "ID": one.get("ID", ""),
            "Phone": one.get("Phone", "")
        }]
    except Exception:
        return []


def get_user_profile_names() -> list:
    """คืนรายชื่อโปรไฟล์ (Name) ทั้งหมด"""
    try:
        profiles = load_user_profiles()
        names = []
        for item in profiles:
            if isinstance(item, dict):
                name = str(item.get("Name", "")).strip()
                if name:
                    names.append(name)
        return names
    except Exception:
        return []


def load_user_profile_by_name(name: str | None) -> dict:
    """โหลดโปรไฟล์ตามชื่อ ถ้าไม่ระบุหรือไม่พบให้คืนโปรไฟล์เดิมแบบ single (load_user_profile)"""
    try:
        if not name:
            return load_user_profile() or {}
        name_s = str(name).strip().lower()
        for item in load_user_profiles():
            if not isinstance(item, dict):
                continue
            nm = str(item.get("Name", "")).strip().lower()
            if nm == name_s:
                return {
                    "Firstname": item.get("Firstname", ""),
                    "Lastname": item.get("Lastname", ""),
                    "Gender": item.get("Gender", ""),
                    "ID": item.get("ID", ""),
                    "Phone": item.get("Phone", "")
                }
        return load_user_profile() or {}
    except Exception:
        return load_user_profile() or {}


# ---------- Google Sheet License/Quota (พื้นฐาน) ----------
LICENSE_SHEET_NAME = "Licenses"


def _ensure_worksheet(spreadsheet, name: str, headers: list[str]):
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=max(10, len(headers)))
        ws.append_row(headers)
    return ws


# ---------- Top-up helpers ----------

def _ensure_topup_sheet(client):
    if not SPREADSHEET_KEY:
        raise RuntimeError("Missing SPREADSHEET_KEY environment variable")
    ss = open_google_sheet(client, SPREADSHEET_KEY)
    try:
        ws = ss.worksheet(TOPUP_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=TOPUP_SHEET_NAME, rows=1000, cols=10)
        ws.append_row([
            "TxID",             # unique id
            "Username",        # requester
            "Amount",          # float THB
            "Method",          # Bank Transfer/PromptPay/Other
            "Note",            # optional
            "Status",          # Pending/Approved/Rejected
            "RequestedAtISO",  # created timestamp
            "ProofLink",       # URL to payment proof
            "ReviewedAtISO",   # when processed
            "AdminNote"        # admin comment
        ])
    return ws


def record_topup_request(user_info: dict, amount: float, method: str, note: str | None = None) -> dict:
    """Create a top-up request row in Google Sheet. Returns {TxID, row_index}.
    Status initialized as Pending.
    """
    client = create_gsheet_client()
    ws = _ensure_topup_sheet(client)
    from uuid import uuid4
    txid = str(uuid4())[:8].upper()
    username = str(user_info.get("Username") or "-")
    now_iso = datetime.utcnow().isoformat()
    row = [txid, username, float(amount), str(method), str(note or ""), "Pending", now_iso, "", "", ""]
    ws.append_row(row)
    return {"TxID": txid, "row_index": ws.row_count}


def update_topup_proof(txid: str, proof_link: str) -> bool:
    """Attach proof link to a pending top-up by TxID. Returns True if updated."""
    client = create_gsheet_client()
    ws = _ensure_topup_sheet(client)
    records = ws.get_all_records()
    # header at row 1, data starts at row 2
    for idx, rec in enumerate(records, start=2):
        if str(rec.get("TxID", "")).strip().upper() == str(txid).strip().upper():
            ws.update(f"H{idx}", proof_link)  # ProofLink column
            return True
    return False


def update_topup_status(txid: str, status: str, admin_note: str | None = None) -> bool:
    """Update status for a top-up row by TxID. Returns True if updated.
    Valid status examples: Pending/Approved/Rejected/Paid.
    """
    client = create_gsheet_client()
    ws = _ensure_topup_sheet(client)
    records = ws.get_all_records()
    now_iso = datetime.utcnow().isoformat()
    for idx, rec in enumerate(records, start=2):
        if str(rec.get("TxID", "")).strip().upper() == str(txid).strip().upper():
            ws.update(f"F{idx}", status)          # Status
            ws.update(f"I{idx}", now_iso)         # ReviewedAtISO
            if admin_note is not None:
                ws.update(f"J{idx}", str(admin_note))
            return True
    return False


def update_topup_status_paid(txid: str, amount: float | None, provider: str, provider_txn_id: str) -> bool:
    """Convenience wrapper: mark a TxID as Paid/Approved with provider reference.
    - Verifies the TxID exists; optionally checks amount if provided (must match Amount column).
    - Writes provider info into AdminNote for traceability.
    """
    client = create_gsheet_client()
    ws = _ensure_topup_sheet(client)
    records = ws.get_all_records()
    for idx, rec in enumerate(records, start=2):
        if str(rec.get("TxID", "")).strip().upper() == str(txid).strip().upper():
            # Optional amount check
            if amount is not None:
                try:
                    rec_amt = float(rec.get("Amount", 0))
                    if abs(rec_amt - float(amount)) > 0.0001:
                        # Amount mismatch; do not mark paid
                        return False
                except Exception:
                    return False
            note_prev = str(rec.get("AdminNote", "")).strip()
            note_add = f"Paid via {provider}: {provider_txn_id}"
            admin_note = (note_prev + " | " if note_prev else "") + note_add
            now_iso = datetime.utcnow().isoformat()
            ws.update(f"F{idx}", "Approved")      # Status
            ws.update(f"I{idx}", now_iso)          # ReviewedAtISO
            ws.update(f"J{idx}", admin_note)       # AdminNote
            return True
    return False


class LicenseSession:
    def __init__(self, user: str, device: str, port: int, version: str, max_licenses: int = 1):
        self.user = user
        self.device = device
        self.port = port
        self.version = version
        self.max_licenses = max_licenses
        self.client = None
        self.sheet = None
        self.ws = None
        self.row_index = None
        self._hb_thread = None
        self._stop = threading.Event()

    def start(self) -> bool:
        try:
            self.client = create_gsheet_client()
            self.sheet = open_google_sheet(self.client, SPREADSHEET_KEY)
            self.ws = _ensure_worksheet(
                self.sheet,
                LICENSE_SHEET_NAME,
                [
                    "User", "Device", "Port", "IsOnline", "LastSeenISO",
                    "Version", "Log"
                ],
            )

            # ตรวจสอบ quota ตามผู้ใช้
            records = self.ws.get_all_records()
            online_count = sum(
                1 for r in records
                if str(r.get("User", "")) == self.user and str(r.get("IsOnline", "")).lower() in ["true", "1", "yes"]
            )
            if online_count >= self.max_licenses:
                return False

            # ค้นหาแถวเดิมของ Device+Port เพื่ออัปเดต ถ้าไม่พบให้ append ใหม่
            found_idx = None
            for idx, r in enumerate(records, start=2):  # header อยู่ที่แถว 1
                if str(r.get("User", "")) == self.user and str(r.get("Device", "")) == self.device and str(r.get("Port", "")) == str(self.port):
                    found_idx = idx
                    break

            now_iso = datetime.utcnow().isoformat()
            row = [self.user, self.device, str(self.port), True, now_iso, self.version, "started"]

            if found_idx:
                self.ws.update(f"A{found_idx}:G{found_idx}", [row])
                self.row_index = found_idx
            else:
                self.ws.append_row(row)
                self.row_index = len(records) + 2

            # start heartbeat thread
            self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._hb_thread.start()
            return True
        except Exception:
            return False

    def _heartbeat_loop(self):
        try:
            while not self._stop.is_set():
                try:
                    now_iso = datetime.utcnow().isoformat()
                    self.ws.update(f"D{self.row_index}:E{self.row_index}", [[True, now_iso]])
                except Exception:
                    pass
                time.sleep(30)
        except Exception:
            pass

    def update_log(self, message: str):
        try:
            self.ws.update(f"G{self.row_index}", message)
        except Exception:
            pass

    def stop(self):
        self._stop.set()
        try:
            now_iso = datetime.utcnow().isoformat()
            self.ws.update(f"D{self.row_index}:E{self.row_index}", [[False, now_iso]])
        except Exception:
            pass


def start_license_session(user_info: dict, port: int, version: str = "1.0") -> LicenseSession | None:
    try:
        username = user_info.get("Username", "-")
        device = os.environ.get("COMPUTERNAME", os.environ.get("HOSTNAME", "device"))
        try:
            max_licenses = int(str(user_info.get("สามาถตั้งจองล่วงหน้าได้กี่ site", "1")).strip() or "1")
        except Exception:
            max_licenses = 1
        session = LicenseSession(username, device, port, version, max_licenses=max_licenses)
        if session.start():
            return session
        return None
    except Exception:
        return None
