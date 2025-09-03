# utils.py  â€”  Cloudflare Worker client (Auth/Config/Topup/Booking/License)
from __future__ import annotations
import os, json, time, threading, socket
from pathlib import Path
from typing import Any, Dict, Optional, List
import requests

# ========= BASIC CONFIG =========
BACKEND_URL = os.getenv("BACKEND_BASE_URL", "https://popmart-worker.bokkchoypayment.workers.dev").rstrip("/")

def _num_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

HTTP_TIMEOUT = _num_env("HTTP_TIMEOUT_SEC", 10)

# à¹ƒà¸Šà¹‰à¹€à¸‰à¸žà¸²à¸° endpoint à¸ à¸²à¸¢à¹ƒà¸™ (à¸–à¹‰à¸²à¸„à¸¸à¸“à¹€à¸£à¸µà¸¢à¸ /internal/* à¸ˆà¸²à¸à¹à¸­à¸›)
INTERNAL_AUTH = os.getenv("INTERNAL_AUTH_SECRET", "")

# ========= /config/all (KV) with ETag cache =========
_CFG_CACHE: Dict[str, Any] = {"data": None, "ts": 0.0, "etag": None}
_CFG_TTL = int(os.getenv("CONFIG_CACHE_SEC", "300"))  # 5 à¸™à¸²à¸—à¸µ

def get_config_all(force: bool=False) -> Dict[str, Any]:
    """à¸”à¸¶à¸‡ config/all à¸ˆà¸²à¸ KV à¸žà¸£à¹‰à¸­à¸¡ ETag+Cache"""
    now = time.time()
    ttl = _num_env("CONFIG_CACHE_SEC", 300)
    if not force and _CFG_CACHE["data"] and (now - _CFG_CACHE["ts"] < ttl):
        return _CFG_CACHE["data"]
    headers = {}
    if _CFG_CACHE["etag"]:
        headers["If-None-Match"] = _CFG_CACHE["etag"]
    r = requests.get(f"{BACKEND_URL}/config/all", headers=headers, timeout=HTTP_TIMEOUT)
    if r.status_code == 304:
        _CFG_CACHE["ts"] = now
        return _CFG_CACHE["data"]
    r.raise_for_status()
    _CFG_CACHE["data"] = r.json()
    _CFG_CACHE["ts"] = now
    _CFG_CACHE["etag"] = r.headers.get("ETag")
    return _CFG_CACHE["data"]

# ========= AUTH: /auth/register /auth/login /auth/me =========
class AuthSession:
    def __init__(self, token: str, username: str, role: str, expires_at: str):
        self.token = token
        self.username = username
        self.role = role
        self.expires_at = expires_at

    @property
    def headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "content-type":"application/json"}

def register(username: str, password: str, email: Optional[str]=None) -> bool:
    """à¸ªà¸¡à¸±à¸„à¸£à¸œà¸¹à¹‰à¹ƒà¸Šà¹‰à¹ƒà¸«à¸¡à¹ˆ (role à¹€à¸£à¸´à¹ˆà¸¡à¸•à¹‰à¸™ normal)"""
    b = {"username": username, "password": password}
    if email: b["email"] = email
    r = requests.post(f"{BACKEND_URL}/auth/register", json=b, timeout=HTTP_TIMEOUT)
    if r.status_code == 409:
        return False
    r.raise_for_status()
    return bool(r.json().get("ok"))

def login(username: str, password: str, device_id: Optional[str]=None) -> Optional[AuthSession]:

    """à¸¥à¹‡à¸­à¸à¸­à¸´à¸™à¹à¸¥à¹‰à¸§à¸„à¸·à¸™ AuthSession (à¹€à¸à¹‡à¸š token à¹„à¸§à¹‰à¹€à¸£à¸µà¸¢à¸ endpoint à¸­à¸·à¹ˆà¸™)"""
    b = {"username": username, "password": password}
    if device_id: b["device_id"] = device_id
    r = requests.post(f"{BACKEND_URL}/auth/login", json=b, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        return None
    j = r.json()
    tok = j.get("token"); user = j.get("username"); role = j.get("role"); exp = j.get("expires_at")
    if not tok or not user:
        return None
    return AuthSession(tok, user, role or "normal", exp or "")

def me(session: AuthSession) -> Dict[str, Any]:
    """à¸”à¸¶à¸‡à¸‚à¹‰à¸­à¸¡à¸¹à¸¥à¸œà¸¹à¹‰à¹ƒà¸Šà¹‰à¸›à¸±à¸ˆà¸ˆà¸¸à¸šà¸±à¸™à¸”à¹‰à¸§à¸¢ Bearer token"""
    r = requests.get(f"{BACKEND_URL}/auth/me", headers=session.headers, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()

# ========= TOPUPS (internal-only for now) =========
def request_topup(username: str, amount: float, method="Manual", description="Top-up") -> str:
    """
    à¹€à¸£à¸µà¸¢à¸ /internal/topups/request â€” à¸•à¹‰à¸­à¸‡à¸¡à¸µ INTERNAL_AUTH
    à¸„à¸·à¸™ TxID à¸ªà¸³à¸«à¸£à¸±à¸šà¸™à¸³à¹„à¸›à¸Šà¸³à¸£à¸°/à¹à¸™à¸šà¸«à¸¥à¸±à¸à¸à¸²à¸™à¸•à¹ˆà¸­à¹„à¸›
    """
    if not INTERNAL_AUTH:
        raise RuntimeError("Missing INTERNAL_AUTH_SECRET (env) for internal endpoint")
    h = {"X-Internal-Auth": INTERNAL_AUTH, "content-type": "application/json"}
    b = {"username": username, "amount": amount, "method": method, "description": description}
    r = requests.post(f"{BACKEND_URL}/internal/topups/request", headers=h, json=b, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    txid = j.get("TxID")
    if not txid:
        raise RuntimeError(f"Topup request failed: {j}")  # à¸à¸±à¸™ response à¹„à¸¡à¹ˆà¸•à¸£à¸‡à¸ªà¹€à¸›à¸„
    return txid

def mark_paid(txid: str, provider="Manual", provider_txn_id: str="") -> bool:
    """à¹€à¸£à¸µà¸¢à¸ /internal/topups/mark-paid à¹€à¸žà¸·à¹ˆà¸­à¹€à¸›à¸¥à¸µà¹ˆà¸¢à¸™à¸ªà¸–à¸²à¸™à¸°à¹€à¸›à¹‡à¸™ Approved à¹à¸¥à¸°à¸­à¸±à¸›à¹€à¸”à¸• role à¸–à¹‰à¸²à¸ˆà¸³à¸™à¸§à¸™à¸•à¸£à¸‡ ROLE_MAP_JSON"""
    if not INTERNAL_AUTH:
        raise RuntimeError("Missing INTERNAL_AUTH_SECRET (env) for internal endpoint")
    h = {"X-Internal-Auth": INTERNAL_AUTH, "content-type":"application/json"}
    b = {"txid": txid, "provider": provider, "provider_txn_id": provider_txn_id}
    r = requests.post(f"{BACKEND_URL}/internal/topups/mark-paid", headers=h, json=b, timeout=HTTP_TIMEOUT)
    if r.status_code != 200: return False
    return bool(r.json().get("ok", True))

# ========= TODAY BOOKING (optional: à¹ƒà¸«à¹‰ backend à¸¡à¸µ endpoint à¸™à¸µà¹‰) =========
_TODAY_CACHE: Dict[str, Any] = {"val": None, "ts": 0.0}
_TODAY_TTL = _num_env("TODAYBOOKING_CACHE_SEC", 60)

def is_today_booking_open(force: bool = False) -> bool:
    """
    à¸–à¹‰à¸² backend à¸¡à¸µ /todaybooking/open -> à¹ƒà¸Šà¹‰à¹€à¸¥à¸¢
    à¸–à¹‰à¸²à¸¢à¸±à¸‡à¹„à¸¡à¹ˆà¸¡à¸µ endpoint à¸™à¸µà¹‰ à¸Ÿà¸±à¸‡à¸à¹Œà¸Šà¸±à¸™à¸ˆà¸°à¸„à¸·à¸™ False à¹€à¸›à¹‡à¸™à¸„à¹ˆà¸²à¹€à¸£à¸´à¹ˆà¸¡à¸•à¹‰à¸™
    """
    now = time.time()
    if not force and _TODAY_CACHE["val"] is not None and (now - _TODAY_CACHE["ts"] < _TODAY_TTL):
        return bool(_TODAY_CACHE["val"])
    r = requests.get(f"{BACKEND_URL}/todaybooking/open", timeout=HTTP_TIMEOUT)
    if r.status_code == 404:
        val = False
    else:
        r.raise_for_status()
        val = bool(r.json().get("open", False))
    _TODAY_CACHE.update({"val": val, "ts": now})
    return val

# ========= LICENSE (à¹€à¸•à¸£à¸µà¸¢à¸¡à¹„à¸§à¹‰ à¸–à¹‰à¸²à¸„à¸¸à¸“à¹€à¸žà¸´à¹ˆà¸¡ endpoint à¸à¸±à¹ˆà¸‡ backend) =========
class LicenseClient:
    """
    à¹ƒà¸Šà¹‰à¹€à¸¡à¸·à¹ˆà¸­ backend à¸¡à¸µ /license/claim /license/heartbeat /license/release à¹à¸¥à¹‰à¸§
    """
    def __init__(self, session: AuthSession, device_id: str, port: int, max_concurrent: int=1):
        self.session = session
        self.device_id = device_id
        self.port = port
        self.max = max_concurrent
        self.license_id: Optional[str] = None
        self._t: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def claim(self) -> bool:
        r = requests.post(f"{BACKEND_URL}/license/claim",
                          headers=self.session.headers,
                          json={"device": self.device_id, "port": self.port, "max": self.max},
                          timeout=HTTP_TIMEOUT)
        if r.status_code != 200: return False
        j = r.json()
        ok = bool(j.get("ok"))
        if ok:
            self.license_id = j.get("id")
            self._start_heartbeat()
        return ok

    def _start_heartbeat(self):
        def run():
            while not self._stop.is_set():
                try:
                    requests.post(f"{BACKEND_URL}/license/heartbeat",
                                  headers=self.session.headers,
                                  json={"id": self.license_id}, timeout=HTTP_TIMEOUT)
                except Exception:
                    pass
                self._stop.wait(20.0)
        self._t = threading.Thread(target=run, daemon=True)
        self._t.start()

    def release(self):
        try:
            self._stop.set()
            if self.license_id:
                requests.post(f"{BACKEND_URL}/license/release",
                              headers=self.session.headers,
                              json={"id": self.license_id}, timeout=HTTP_TIMEOUT)
        finally:
            self.license_id = None
    # Small adapter for callers expecting stop()
    def stop(self):
        self.release()

# ========= QUICK DEMO (optional) =========
if __name__ == "__main__":
    # 1) à¹‚à¸«à¸¥à¸” config (selectors/branches/times)
    cfg = get_config_all()
    print("sites:", list(cfg.get("sites", {}).keys()))
    print("branches:", len(cfg.get("branches", [])), "times:", len(cfg.get("times", [])))

    # 2) à¸ªà¸¡à¸±à¸„à¸£/à¸¥à¹‡à¸­à¸à¸­à¸´à¸™ (à¸¥à¸­à¸‡à¹ƒà¸Šà¹‰ account à¸—à¸”à¸ªà¸­à¸šà¸‚à¸­à¸‡à¸„à¸¸à¸“)
    # register("alice","P@ssw0rd!","alice@example.com")
    sess = login("alice","P@ssw0rd!", device_id="DESKTOP-1234")
    if not sess:
        raise SystemExit("login failed")
    print("logged in as:", sess.username, sess.role)

    # 3) à¸•à¸±à¸§à¸­à¸¢à¹ˆà¸²à¸‡ topup (à¸–à¹‰à¸²à¸•à¸±à¹‰à¸‡ INTERNAL_AUTH_SECRET à¹à¸¥à¹‰à¸§)
    if INTERNAL_AUTH:
        txid = request_topup(sess.username, 1500, method="Manual", description="Test topup")
        print("TxID:", txid)
        ok = mark_paid(txid, provider="Manual", provider_txn_id="txn-001")
        print("mark paid:", ok)

    # 4) today booking (à¸«à¸²à¸ backend à¸¢à¸±à¸‡à¹„à¸¡à¹ˆà¸¡à¸µ endpoint à¸ˆà¸°à¹„à¸”à¹‰ False)
    print("today open:", is_today_booking_open())

# ========= Compatibility helpers for GUI (file I/O + wrappers) =========

def _company_dir() -> Path:
    """Return app data directory used by the GUI and schedulers.
    On Windows, use %APPDATA%/BokkChoYCompany. Else, use ~/.BokkChoYCompany.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "BokkChoYCompany"
    else:
        p = Path.home() / ".BokkChoYCompany"
    p.mkdir(parents=True, exist_ok=True)
    return p

def setup_config_files() -> None:
    """Ensure expected JSON files exist in the company dir with sane defaults."""
    base = _company_dir()
    defaults = {
        "line_data.json": {},               # may be dict {email: password} or list in legacy
        "user_profile.json": {},            # single default user profile
        "user_profiles.json": [],           # list of named profiles
        "scheduled_tasks.json": [],         # scheduler tasks
    }
    for name, default in defaults.items():
        fp = base / name
        if not fp.exists():
            try:
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(default, f, ensure_ascii=False, indent=4)
            except Exception:
                # best effort; GUI handles absence too
                pass

def load_line_credentials() -> Dict[str, str]:
    """Load LINE credentials from line_data.json and normalize to {email: password} mapping.
    Supports legacy formats: list of {Email,Password} or a single dict.
    """
    path = _company_dir() / "line_data.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            # Could be {Email,Password} or {email: password} mapping
            if ("Email" in raw or "email" in raw) and ("Password" in raw or "password" in raw):
                email = raw.get("Email") or raw.get("email") or ""
                password = raw.get("Password") or raw.get("password") or ""
                return {email: password} if (email and password) else {}
            return {str(k): str(v) for k, v in raw.items()}
        if isinstance(raw, list):
            result: Dict[str, str] = {}
            for item in raw:
                if not isinstance(item, dict):
                    continue
                em = (item.get("Email") or item.get("email") or "").strip()
                pw = (item.get("Password") or item.get("password") or "").strip()
                if em and pw:
                    result[em] = pw
            return result
    except Exception:
        return {}
    return {}

def load_user_profile() -> Dict[str, Any]:
    """Load single default user profile from user_profile.json."""
    path = _company_dir() / "user_profile.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _load_user_profiles_list() -> List[Dict[str, Any]]:
    path = _company_dir() / "user_profiles.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def get_user_profile_names() -> List[str]:
    """Return list of profile display names from user_profiles.json."""
    profs = _load_user_profiles_list()
    names = []
    for rec in profs:
        if isinstance(rec, dict):
            nm = str(rec.get("Name") or "").strip()
            if nm:
                names.append(nm)
    return names

def load_user_profile_by_name(name: Optional[str]) -> Dict[str, Any]:
    """Load a profile by name from user_profiles.json; fallback to user_profile.json if not found or name is empty."""
    sel = (name or "").strip()
    if sel:
        for rec in _load_user_profiles_list():
            if not isinstance(rec, dict):
                continue
            nm = str(rec.get("Name") or "").strip()
            if nm and nm == sel:
                return {
                    "Firstname": rec.get("Firstname", ""),
                    "Lastname": rec.get("Lastname", ""),
                    "Gender": rec.get("Gender", ""),
                    "ID": rec.get("ID", ""),
                    "Phone": rec.get("Phone", ""),
                }
    return load_user_profile()

def register_user(username: str, password: str, role: str = "normal", max_sites: int = 0, can_schedule: str = "à¹„à¸¡à¹ˆ") -> Dict[str, Any]:
    """Register user via backend and return a GUI-friendly record.
    Extra parameters are accepted for compatibility but not sent unless backend supports them.
    """
    ok = register(username=username, password=password, email=None)
    if not ok:
        raise RuntimeError("Username already exists or registration failed")
    return {"Username": username, "Role": role}

def get_all_api_data() -> Dict[str, Any]:
    """Fetch consolidated config from backend and adapt keys to the GUI expectations.
    Returns a dict containing:
    - 'branchs': list of branch names (legacy key spelling)
    - 'times': list of time strings
    - 'pmrocket'/'ithitec'/'rocketbooking': site selector maps
    """
    # Use safe-config fetcher with robust TTL parsing
    try:
        cfg = get_config_all_safe()
    except Exception:
        cfg = get_config_all()
    sites = cfg.get("sites", {}) if isinstance(cfg, dict) else {}
    def site(name: str) -> Dict[str, Any]:
        if isinstance(sites, dict) and isinstance(sites.get(name), dict):
            return sites.get(name) or {}
        return cfg.get(name, {}) if isinstance(cfg.get(name, {}), dict) else {}
    return {
        "branchs": cfg.get("branches", cfg.get("branchs", [])) or [],
        "times": cfg.get("times", []) or [],
        "pmrocket": site("pmrocket"),
        "ithitec": site("ithitec"),
        "rocketbooking": site("rocketbooking"),
    }

def get_config_all_safe(force: bool=False) -> Dict[str, Any]:
    """Fetch /config/all with ETag cache, using safe TTL parsing from env."""
    now = time.time()
    ttl = _num_env("CONFIG_CACHE_SEC", 300)
    if not force and _CFG_CACHE["data"] and (now - _CFG_CACHE["ts"] < ttl):
        return _CFG_CACHE["data"]
    headers = {}
    if _CFG_CACHE["etag"]:
        headers["If-None-Match"] = _CFG_CACHE["etag"]
    r = requests.get(f"{BACKEND_URL}/config/all", headers=headers, timeout=HTTP_TIMEOUT)
    if r.status_code == 304 and _CFG_CACHE["data"] is not None:
        _CFG_CACHE["ts"] = now
        return _CFG_CACHE["data"]
    r.raise_for_status()
    try:
        data = r.json()
    except Exception:
        data = {}
    _CFG_CACHE["data"] = data
    _CFG_CACHE["ts"] = now
    _CFG_CACHE["etag"] = r.headers.get("ETag") or r.headers.get("etag")
    return data

def google_sheet_check_login(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Compatibility shim: validate credentials via backend login instead of Google Sheet.
    Returns a GUI-style user_info dict on success, "expired" on expiry, or None on failure.
    """
    sess = login(username=username, password=password, device_id=socket.gethostname())
    if not sess:
        return None
    # Try /auth/me for richer info; fall back to session fields
    extra = {}
    try:
        extra = me(sess) or {}
    except Exception:
        extra = {}
    role = str(extra.get("role") or sess.role or "normal").strip().lower()
    expires_at = str(extra.get("expires_at") or sess.expires_at or "")
    # Basic policy for scheduler capability; adjust as needed.
    can_sched = "à¹ƒà¸Šà¹ˆ" if role in {"admin", "staff", "premium"} else "à¹„à¸¡à¹ˆ"
    max_sites = 3 if role in {"admin", "staff", "premium"} else 0
    return {
        "Username": sess.username,
        "Role": role,
        "Expiration date": expires_at,
        "à¸•à¸±à¹‰à¸‡à¸ˆà¸­à¸‡à¸¥à¹ˆà¸§à¸‡à¸«à¸™à¹‰à¸²à¹„à¸”à¹‰à¹„à¸«à¸¡": can_sched,
        "à¸ªà¸²à¸¡à¸²à¸–à¸•à¸±à¹‰à¸‡à¸ˆà¸­à¸‡à¸¥à¹ˆà¸§à¸‡à¸«à¸™à¹‰à¸²à¹„à¸”à¹‰à¸à¸µà¹ˆ site": max_sites,
        # expose token for license session
        "token": sess.token,
    }

def start_license_session(user_info: Dict[str, Any], port: int, version: str = "1.0") -> Optional[LicenseClient]:
    """Start a license (quota) session if backend supports it. Returns a LicenseClient or None.
    Expects user_info to include 'token'.
    """
    token = (user_info or {}).get("token")
    username = (user_info or {}).get("Username") or "user"
    if not token:
        return None
    try:
        sess = AuthSession(token=token, username=username, role=(user_info or {}).get("Role", ""), expires_at=(user_info or {}).get("Expiration date", ""))
        client = LicenseClient(session=sess, device_id=socket.gethostname() or username, port=int(port or 0), max_concurrent=1)
        ok = client.claim()
        return client if ok else None
    except Exception:
        return None


