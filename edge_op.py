# edge_op.py
import subprocess
import os
import sys
import socket
from pathlib import Path

def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """ตรวจสอบว่าพอร์ตกำลังถูกใช้งานอยู่หรือไม่"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0

def _find_free_port(start: int = 9222, end: int = 9322) -> int:
    """ค้นหาพอร์ตที่ว่างในช่วงที่กำหนด"""
    for p in range(start, end + 1):
        if not _is_port_in_use(p):
            return p
    raise RuntimeError(f"ไม่พบพอร์ตที่ว่างในช่วง {start}-{end}")

def _make_user_data_dir_for_profile(base_dir: Path, profile_name: str) -> str:
    """
    สร้างโฟลเดอร์ user-data-dir แยกสำหรับแต่ละ profile
    """
    target = base_dir / f"user_data_{profile_name.replace(' ', '_')}"
    target.mkdir(parents=True, exist_ok=True)
    return str(target)

def launch_edge_with_profile(profile: str, 
                             url: str = "https://popmartth.rocket-booking.app/booking", 
                             remote_debugging_port: int | None = None) -> tuple[int, subprocess.Popen]:
    """
    เปิด Microsoft Edge พร้อม Profile ที่กำหนดและเปิด Remote Debugging
    """
    possible_edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    edge_path = next((p for p in possible_edge_paths if os.path.exists(p)), None)
    if not edge_path:
        raise FileNotFoundError("ไม่พบไฟล์ msedge.exe กรุณาตรวจสอบตำแหน่งการติดตั้ง")

    if remote_debugging_port is None or _is_port_in_use(remote_debugging_port):
        remote_debugging_port = _find_free_port()

    cwd = Path.cwd()
    user_data_dir = _make_user_data_dir_for_profile(cwd / "edge_profiles", profile)

    flags = [
        edge_path,
        f"--remote-debugging-port={remote_debugging_port}",
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile}",
        "--no-first-run",
        "--disable-extensions",
        "--no-sandbox",
        url
    ]
    
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = 0x00000008 | 0x00000200  # detached

    proc = subprocess.Popen(flags,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             creationflags=creationflags if creationflags else 0)
    print(f"✅ เปิด Edge Profile='{profile}' ที่พอร์ต={remote_debugging_port} user_data_dir='{user_data_dir}'")
    
    return remote_debugging_port, proc

def launch_multiple_profiles(profiles: list[str], url: str):
    """
    เปิด Edge หลาย instance ให้แต่ละ profile ได้พอร์ต remote debugging แยก
    คืน dict: profile -> {'port': int, 'process': Popen, 'user_data_dir': str}
    """
    result = {}
    for p in profiles:
        port, proc = launch_edge_with_profile(profile=p, url=url)
        result[p] = {
            "port": port,
            "process": proc,
            "user_data_dir": f"{Path.cwd() / 'edge_profiles' / f'user_data_{p.replace(' ', '_')}' }"
        }
    return result