import requests
import gspread
from google.oauth2.service_account import Credentials

# Constants
API_KEYS = {
    "branchs": "69fa5371392bdfe7160f378ef4b10bb6",
    "pmrocket": "0857df816fa1952d96c6b76762510516",
    "rocketbooking": "8155bfa0c8faaed0a7917df38f0238b6",
    "times": "1582b63313475631d732f4d1aed9a534",
    "ithitec": "a48bca796db6089792a2d9047c7ebf78",
    "token": "a2htZW5odWFrdXltYWV5ZWQ="
}
BASE_URL = "https://backend-secure-cred-api.onrender.com/get-credentials"

# โหลด Google API credentials.json จาก backend
def get_google_credentials_json():
    token = API_KEYS["token"]
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
