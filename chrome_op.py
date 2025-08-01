# chrome_op.py
import subprocess
import os
import sys
import socket
from pathlib import Path

def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0

def _find_free_port(start: int = 9222, end: int = 9322) -> int:
    for p in range(start, end + 1):
        if not _is_port_in_use(p):
            return p
    raise RuntimeError(f"No free port in range {start}-{end}")

def _make_user_data_dir_for_profile(base_dir: Path, profile_name: str) -> str:
    """
    สร้างโฟลเดอร์ user-data-dir แยกสำหรับแต่ละ profile
    """
    target = base_dir / f"user_data_{profile_name.replace(' ', '_')}"
    target.mkdir(parents=True, exist_ok=True)
    return str(target)

def launch_chrome_instance(profile: str,
                           url: str = "https://popmartth.rocket-booking.app/booking",
                           remote_debugging_port: int | None = None) -> tuple[int, subprocess.Popen]:
    """
    เปิด Google Chrome พร้อม Profile ที่กำหนดและเปิด Remote Debugging
    """
    possible_chrome_paths = [
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    ]
    chrome_path = next((p for p in possible_chrome_paths if os.path.exists(p)), None)
    if not chrome_path:
        raise FileNotFoundError("Chrome executable not found.")

    if remote_debugging_port is None or _is_port_in_use(remote_debugging_port):
        remote_debugging_port = _find_free_port()

    cwd = Path.cwd()
    user_data_dir = _make_user_data_dir_for_profile(cwd / "chrome_profiles", profile)

    flags = [
        chrome_path,
        f"--remote-debugging-port={remote_debugging_port}",
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile}",
        "--no-first-run",
        "--disable-extensions",
        url
    ]

    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = 0x00000008 | 0x00000200  # detached

    proc = subprocess.Popen(flags,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             creationflags=creationflags if creationflags else 0)
    print(f"✅ Launched Chrome profile='{profile}' port={remote_debugging_port} user_data_dir='{user_data_dir}'")
    return remote_debugging_port, proc

def launch_multiple_profiles(profiles: list[str], url: str):
    """
    เปิด Chrome หลาย instance ให้แต่ละ profile ได้พอร์ต remote debugging แยก
    คืน dict: profile -> {'port': int, 'process': Popen, 'user_data_dir': str}
    """
    result = {}
    for p in profiles:
        port, proc = launch_chrome_instance(profile=p, url=url)
        result[p] = {
            "port": port,
            "process": proc,
            "user_data_dir": f"{Path.cwd() / 'chrome_profiles' / f'user_data_{p.replace(' ', '_')}' }"
        }
    return result