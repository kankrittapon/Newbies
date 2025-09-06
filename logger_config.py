# logger_config.py
import logging
import os
from datetime import datetime
from pathlib import Path

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """ตั้งค่า logging system"""
    
    # สร้าง logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # สร้างชื่อไฟล์ log ตามวันที่
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"newbies_bot_{today}.log"
    
    # ตั้งค่า formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # ลบ handlers เก่า
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    
    # Console handler (เฉพาะ WARNING ขึ้นไป)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    root_logger.addHandler(console_handler)
    
    # สร้าง app logger
    app_logger = logging.getLogger("newbies_bot")
    app_logger.info("=== Newbies Bot Started ===")
    
    return app_logger

def get_logger(name: str = "newbies_bot") -> logging.Logger:
    """ได้ logger instance"""
    return logging.getLogger(name)

# Performance logger สำหรับ track ประสิทธิภาพ
def log_performance(func_name: str, duration: float):
    """Log performance metrics"""
    perf_logger = get_logger("performance")
    if duration > 5.0:  # ช้าเกิน 5 วินาที
        perf_logger.warning(f"{func_name} took {duration:.2f}s (SLOW)")
    else:
        perf_logger.info(f"{func_name} took {duration:.2f}s")

# Cleanup old logs (เก็บแค่ 7 วัน)
def cleanup_old_logs():
    """ลบ log files เก่า"""
    try:
        log_dir = Path("logs")
        if not log_dir.exists():
            return
            
        cutoff_date = datetime.now().timestamp() - (7 * 24 * 60 * 60)  # 7 days
        
        for log_file in log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_date:
                log_file.unlink()
                
    except Exception as e:
        logging.error(f"Failed to cleanup old logs: {e}")