# config_loader.py - Load wizard configuration
import json
from pathlib import Path
from logger_config import get_logger

logger = get_logger()

def load_wizard_config():
    """Load configuration from wizard"""
    try:
        config_dir = Path.home() / ".newbies_bot"
        config_file = config_dir / "wizard_config.json"
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Failed to load wizard config: {e}")
        return {}

def get_default_browser():
    """Get default browser from config"""
    config = load_wizard_config()
    return config.get('browser', {}).get('type', 'Chrome')

def get_default_profile():
    """Get default profile from config"""
    config = load_wizard_config()
    return config.get('browser', {}).get('profile', 'Default')

def get_auto_login_enabled():
    """Check if auto login is enabled"""
    config = load_wizard_config()
    return config.get('user', {}).get('auto_login', False)

def get_saved_credentials():
    """Get saved login credentials"""
    config = load_wizard_config()
    user_config = config.get('user', {})
    
    if user_config.get('auto_login', False):
        return {
            'username': user_config.get('username', ''),
            'password': user_config.get('password', '')
        }
    return None

def get_line_config():
    """Get LINE configuration"""
    config = load_wizard_config()
    return config.get('line', {})

def get_profile_data():
    """Get profile data"""
    config = load_wizard_config()
    return config.get('profile', {})