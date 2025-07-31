# chrome_op.py
import subprocess
import os

def launch_chrome_with_profile(profile: str, url: str = "https://popmartth.rocket-booking.app/booking"):
    chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    remote_debugging_port = 9222

    try:
        subprocess.Popen([
            chrome_path,
            f"--remote-debugging-port={remote_debugging_port}",
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile}",
            url
        ])
        print(f"✅ Launched Chrome with profile: {profile}")
    except Exception as e:
        print(f"❌ Failed to launch Chrome: {e}")
