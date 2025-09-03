# admin_console_handlers.py (หรือวางในไฟล์ GUI เดิม)
from utils_admin import (
    me, admin_users_list, admin_users_update, admin_users_create,
    admin_users_delete, admin_users_reset_password,
    today_list, today_set, today_bulk_set
)

def refresh_users():
    info = me()  # ตรวจสิทธิ์/role
    if (info.get("role") or "").lower() != "admin":
        raise RuntimeError("ต้องเป็น admin เท่านั้น")
    data = admin_users_list(page=1, page_size=100)
    return data["items"]

def save_user_edits(username, role, sites_limit, can_prebook, exp_date, email):
    return admin_users_update(
        username=username,
        role=role,
        sites_limit=int(sites_limit),
        can_prebook=bool(can_prebook),
        exp_date=(exp_date or None),
        email=(email or None),
    )

def create_user(username, password, role="normal"):
    return admin_users_create(username=username, password=password, role=role)

def delete_user(username):
    return admin_users_delete(username=username)

def reset_password(username, new_password):
    return admin_users_reset_password(username=username, new_password=new_password)

def get_today_range(date_from, date_to):
    return today_list(date_from, date_to)

def set_today(date_ymd, open_flag):
    return today_set(date_ymd, bool(open_flag))

def bulk_set_today(items):
    # items = [{"date": "2025-09-05", "open": True}, ...]
    return today_bulk_set(items)
