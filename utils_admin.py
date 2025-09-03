# utils_admin.py
import os, time, json, requests
from typing import Any, Dict, List, Optional, Tuple

WORKER_BASE = os.getenv("POP_WORKER_BASE", "https://popmart-worker.bokkchoypayment.workers.dev")

# ===== in-memory state =====
_TOKEN: Optional[str] = None
_TOKEN_EXP: Optional[float] = None

# Config cache (+ ETag)
_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_CONFIG_ETAG: Optional[str] = None
_CONFIG_TS: float = 0.0

def _num_env(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)))
        return v
    except Exception:
        return default

HTTP_TIMEOUT = _num_env("HTTP_TIMEOUT_SEC", 10)
CONFIG_CACHE_SEC = _num_env("CONFIG_CACHE_SEC", 300)         # 5 นาที
TODAYBOOKING_CACHE_SEC = _num_env("TODAYBOOKING_CACHE_SEC", 30)

def _headers(auth: bool = False) -> Dict[str, str]:
    h = {"content-type": "application/json"}
    if auth and _TOKEN:
        h["authorization"] = f"Bearer {_TOKEN}"
    return h

# ---------- Auth ----------
def login(username: str, password: str, device_id: Optional[str] = None) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/auth/login"
    body = {"username": username, "password": password}
    if device_id:
        body["device_id"] = device_id
    r = requests.post(url, data=json.dumps(body), headers=_headers(), timeout=HTTP_TIMEOUT)
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"login failed: bad JSON (status={r.status_code})")
    if not r.ok:
        raise RuntimeError(j.get("error") or "login failed")
    # keep token only in memory
    global _TOKEN, _TOKEN_EXP
    _TOKEN = j.get("token")
    # ไม่บังคับใช้ expires_at ใน client แต่สามารถเก็บเผื่อหมดอายุก็ได้
    _TOKEN_EXP = time.time() + 3600 * 24 * 30
    return j

def me() -> Dict[str, Any]:
    url = f"{WORKER_BASE}/auth/me"
    r = requests.get(url, headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "unauthorized")
    return j

# ---------- Config (KV) ----------
def get_config_all(force: bool = False) -> Dict[str, Any]:
    global _CONFIG_CACHE, _CONFIG_ETAG, _CONFIG_TS
    now = time.time()
    if not force and _CONFIG_CACHE and (now - _CONFIG_TS) < CONFIG_CACHE_SEC:
        return _CONFIG_CACHE

    url = f"{WORKER_BASE}/config/all"
    h = _headers()
    if _CONFIG_ETAG:
        h["If-None-Match"] = _CONFIG_ETAG
    r = requests.get(url, headers=h, timeout=HTTP_TIMEOUT)
    if r.status_code == 304 and _CONFIG_CACHE:
        _CONFIG_TS = now
        return _CONFIG_CACHE
    if not r.ok:
        raise RuntimeError(f"config/all failed: {r.text}")
    try:
        j = r.json()
    except Exception:
        raise RuntimeError("config/all: bad JSON")
    _CONFIG_CACHE = j
    _CONFIG_ETAG = r.headers.get("etag")
    _CONFIG_TS = now
    return j

# ---------- Admin: Users ----------
def admin_users_list(search: str = "", page: int = 1, page_size: int = 50,
                     sort: str = "updated_at desc") -> Dict[str, Any]:
    url = f"{WORKER_BASE}/admin/users"
    params = {
        "search": search,
        "page": page,
        "page_size": page_size,
        "sort": sort
    }
    r = requests.get(url, headers=_headers(auth=True), params=params, timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "list users failed")
    return j

def admin_users_update(username: str, **fields) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/admin/users/update"
    body = {"username": username}
    # allow: role, sites_limit, can_prebook, exp_date, email
    for k in ["role", "sites_limit", "can_prebook", "exp_date", "email"]:
        if k in fields:
            body[k] = fields[k]
    r = requests.post(url, data=json.dumps(body), headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "update user failed")
    return j

def admin_users_create(username: str, password: str, **fields) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/admin/users/create"
    body = {"username": username, "password": password}
    for k in ["role", "sites_limit", "can_prebook", "exp_date", "email"]:
        if k in fields:
            body[k] = fields[k]
    r = requests.post(url, data=json.dumps(body), headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "create user failed")
    return j

def admin_users_delete(username: str) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/admin/users/delete"
    r = requests.post(url, data=json.dumps({"username": username}), headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "delete user failed")
    return j

def admin_users_reset_password(username: str, new_password: str) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/admin/users/reset-password"
    r = requests.post(url, data=json.dumps({"username": username, "new_password": new_password}),
                      headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "reset password failed")
    return j

# ---------- Admin: Todaybooking ----------
def today_list(date_from: str, date_to: str) -> List[Dict[str, Any]]:
    url = f"{WORKER_BASE}/admin/todaybooking/list"
    r = requests.get(url, headers=_headers(auth=True), params={"from": date_from, "to": date_to},
                     timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "list todaybooking failed")
    return j.get("items", [])

def today_set(date: str, open_flag: bool) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/admin/todaybooking/set"
    r = requests.post(url, data=json.dumps({"date": date, "open": bool(open_flag)}),
                      headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "set todaybooking failed")
    return j

def today_bulk_set(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/admin/todaybooking/bulk-set"
    r = requests.post(url, data=json.dumps({"items": items}), headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "bulk-set todaybooking failed")
    return j

# ---------- License (ใช้ใน client ช่วงรัน Playwright) ----------
def license_claim(device: str, port: Optional[int], max_sessions: int = 1) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/license/claim"
    body = {"device": device, "max": max_sessions}
    if port is not None: body["port"] = int(port)
    r = requests.post(url, data=json.dumps(body), headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "license claim failed")
    return j

def license_heartbeat(lic_id: str) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/license/heartbeat"
    r = requests.post(url, data=json.dumps({"id": lic_id}), headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "license heartbeat failed")
    return j

def license_release(lic_id: str) -> Dict[str, Any]:
    url = f"{WORKER_BASE}/license/release"
    r = requests.post(url, data=json.dumps({"id": lic_id}), headers=_headers(auth=True), timeout=HTTP_TIMEOUT)
    j = r.json() if r.content else {}
    if not r.ok:
        raise RuntimeError(j.get("error") or "license release failed")
    return j

# ---------- Optional AdminClient wrapper for GUI ----------
class AdminClient:
    """Thin wrapper used by GUI Admin Console when available.
    Provides a stable method surface mapping to utils_admin functions.
    """
    def __init__(self, base_url: str, token: str):
        self.base_url = (base_url or WORKER_BASE).rstrip("/")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Users
    def list_users(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/admin/users", headers=self.headers, timeout=HTTP_TIMEOUT)
            j = r.json() if r.content else {}
            if isinstance(j, dict) and "items" in j:
                items = list(j.get("items") or [])
                # Normalize fields expected by GUI
                norm = []
                for it in items:
                    if isinstance(it, dict):
                        it = dict(it)
                        if "exp_date" in it and "expires_at" not in it:
                            it["expires_at"] = it.get("exp_date")
                    norm.append(it)
                return norm
            if isinstance(j, list):
                out = []
                for it in j:
                    if isinstance(it, dict) and ("exp_date" in it) and ("expires_at" not in it):
                        it = {**it, "expires_at": it.get("exp_date")}
                    out.append(it)
                return out
        except Exception:
            pass
        return []

    def update_user(self, username: str, fields: Dict[str, Any]) -> bool:
        payload = {**fields}
        # translate GUI keys -> backend keys
        if "expires_at" in payload and "exp_date" not in payload:
            payload["exp_date"] = payload.pop("expires_at")
        # 'status' is not supported server-side; ignore silently
        payload.pop("status", None)
        try:
            r = requests.post(f"{self.base_url}/admin/users/update", headers=self.headers,
                              data=json.dumps({"username": username, **payload}), timeout=HTTP_TIMEOUT)
            return r.ok
        except Exception:
            return False

    def delete_user(self, username: str) -> bool:
        try:
            r = requests.post(f"{self.base_url}/admin/users/delete", headers=self.headers,
                              data=json.dumps({"username": username}), timeout=HTTP_TIMEOUT)
            return r.ok
        except Exception:
            return False

    # TodayBooking
    def get_todaybooking_open(self) -> Optional[bool]:
        try:
            r = requests.get(f"{self.base_url}/todaybooking/open", headers=self.headers, timeout=HTTP_TIMEOUT)
            if r.status_code == 404:
                return None
            j = r.json() if r.content else {}
            return bool(j.get("open", False))
        except Exception:
            return None

    def set_todaybooking_open(self, open_flag: bool) -> bool:
        # Use admin endpoint; omit date to let backend default to today
        try:
            r = requests.post(f"{self.base_url}/admin/todaybooking/set", headers=self.headers,
                              data=json.dumps({"open": bool(open_flag)}), timeout=HTTP_TIMEOUT)
            return r.ok
        except Exception:
            return False
