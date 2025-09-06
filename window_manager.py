# window_manager.py
import tkinter as tk
from typing import Dict, Optional, Type
import weakref

class WindowManager:
    """จัดการ window lifecycle และป้องกัน memory leaks"""
    _instance = None
    _windows: Dict[str, weakref.ref] = {}
    _current_window: Optional[tk.Tk] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def switch_to(self, window_class: Type[tk.Tk], *args, **kwargs) -> tk.Tk:
        """เปลี่ยน window โดยปิดอันเก่าก่อน"""
        # ปิด window ปัจจุบัน
        if self._current_window and self._current_window.winfo_exists():
            self._current_window.destroy()
        
        # สร้าง window ใหม่
        new_window = window_class(*args, **kwargs)
        self._current_window = new_window
        
        # เก็บ weak reference
        window_name = window_class.__name__
        self._windows[window_name] = weakref.ref(new_window)
        
        return new_window
    
    def get_current(self) -> Optional[tk.Tk]:
        """ได้ window ปัจจุบัน"""
        return self._current_window
    
    def cleanup(self):
        """ทำความสะอาด resources"""
        if self._current_window and self._current_window.winfo_exists():
            self._current_window.destroy()
        self._windows.clear()
        self._current_window = None

# Global instance
window_manager = WindowManager()