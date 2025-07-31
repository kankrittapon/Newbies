import subprocess
import os

def launch_edge_with_profile(profile: str, url: str = "https://popmartth.rocket-booking.app/booking"):
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")

    try:
        subprocess.Popen([
            edge_path,
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile}",
            url
        ])
        print(f"✅ Launched Edge with profile: {profile}")
    except Exception as e:
        print(f"❌ Failed to launch Edge: {e}")
