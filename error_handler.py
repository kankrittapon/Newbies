# error_handler.py
import traceback
import functools
from tkinter import messagebox
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

def safe_execute(show_error: bool = True, default_return: Any = None):
    """Decorator สำหรับ handle errors อย่างปลอดภัย"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                
                if show_error:
                    error_msg = f"เกิดข้อผิดพลาด: {str(e)}"
                    messagebox.showerror("ข้อผิดพลาด", error_msg)
                
                return default_return
        return wrapper
    return decorator

def handle_async_error(callback_func: Callable = None):
    """Handle errors ใน async operations"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Async error in {func.__name__}: {e}", exc_info=True)
                if callback_func:
                    callback_func(f"❌ {str(e)}")
                raise
        return wrapper
    return decorator

class ErrorReporter:
    """รวบรวมและรายงาน errors"""
    
    @staticmethod
    def report_critical(error: Exception, context: str = ""):
        """รายงาน critical errors"""
        error_details = {
            'error': str(error),
            'context': context,
            'traceback': traceback.format_exc()
        }
        logger.critical(f"Critical error: {error_details}")
        
        # แสดง error dialog
        msg = f"เกิดข้อผิดพลาดร้ายแรง\n\n{context}\n\nError: {str(error)}"
        messagebox.showerror("ข้อผิดพลาดร้ายแรง", msg)
    
    @staticmethod
    def report_warning(message: str):
        """รายงาน warnings"""
        logger.warning(message)
        messagebox.showwarning("คำเตือน", message)