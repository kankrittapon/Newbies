# 🎯 Newbies Bot

**ระบบจองอัตโนมัติที่ใช้งานง่าย สำหรับผู้เริ่มต้นและผู้เชี่ยวชาญ**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/your-repo/newbies-bot)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## ✨ Features

### 🎯 **Simple Mode** - สำหรับผู้เริ่มต้น
- จองใน 3 ขั้นตอนง่ายๆ
- การตั้งค่าอัตโนมัติ
- UI ที่เข้าใจง่าย

### ⚙️ **Advanced Mode** - สำหรับผู้เชี่ยวชาญ
- ตั้งค่าละเอียด (Round, Timer, Delay)
- Smart Fallback System
- Multi-Profile Support
- Scheduler (VIP Feature)

### 🔧 **Performance & Stability**
- Error Handling System
- Comprehensive Logging
- Memory Management
- Window Lifecycle Control

### 🧙♂️ **Configuration Wizard**
- First-time Setup Guide
- Auto Configuration
- User-friendly Interface

## 🚀 Quick Start

### 1. ดาวน์โหลดและติดตั้ง
```bash
# ดาวน์โหลด NewbiesBot.exe
# คลิกขวา → Run as administrator (ครั้งแรก)
```

### 2. Configuration Wizard
- ทำตาม 6 ขั้นตอนใน Setup Wizard
- ตั้งค่าข้อมูลผู้ใช้, LINE, โปรไฟล์, เบราว์เซอร์

### 3. เริ่มใช้งาน
```
หน้าหลัก → 🎯 โหมดง่าย (แนะนำ)
→ เลือกสาขา → เลือกวัน/เวลา → 🚀 เริ่มจอง
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [📖 User Manual](USER_MANUAL.md) | คู่มือการใช้งานฉบับสมบูรณ์ |
| [🛠️ Setup Guide](SETUP_GUIDE.md) | คู่มือการติดตั้งและตั้งค่า |
| [🔧 Troubleshooting](TROUBLESHOOTING.md) | การแก้ไขปัญหาที่พบบ่อย |
| [🏗️ Build Guide](README_BUILD.md) | การ Build จาก Source Code |

## 🎮 Usage Examples

### Simple Mode (แนะนำสำหรับผู้เริ่มต้น)
```
1. เลือกสาขา: "Central World"
2. เลือกวัน: "15"
3. เลือกเวลา: "10:00"
4. กด "🚀 เริ่มจอง"
```

### Advanced Mode (สำหรับผู้เชี่ยวชาญ)
```
- Site: ROCKETBOOKING
- Browser: Chrome (Profile 1)
- Branch: Central World
- Day: 15
- Time: 10:00
- Round: 2 (ปุ่มเวลาลำดับที่ 2)
- Timer: 5 sec (รอปุ่ม Register)
- Delay: 1 sec (หน่วงก่อนคลิก)
- Smart Fallback: ✅ (ใช้สาขา/เวลาสำรอง)
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│                GUI Layer                │
├─────────────────────────────────────────┤
│  Simple Mode  │  Advanced Mode  │ Admin │
├─────────────────────────────────────────┤
│            Core Services                │
│  • Window Manager                       │
│  • Error Handler                        │
│  • Logger System                        │
│  • Config Loader                        │
├─────────────────────────────────────────┤
│           Browser Control               │
│  • Chrome Operations                    │
│  • Edge Operations                      │
├─────────────────────────────────────────┤
│            Booking Engine               │
│  • Real Booking                         │
│  • Trial Booking                        │
│  • Scheduler                            │
│  • LINE Auto Login                      │
└─────────────────────────────────────────┘
```

## 🔧 System Requirements

- **OS:** Windows 10/11 (64-bit)
- **RAM:** 4GB+ (แนะนำ 8GB)
- **Storage:** 500MB
- **Browser:** Chrome หรือ Edge (เวอร์ชันล่าสุด)
- **Internet:** 10 Mbps+

## 📦 Installation

### Option 1: Executable (แนะนำ)
1. ดาวน์โหลด `NewbiesBot.exe`
2. Run as administrator
3. ทำตาม Configuration Wizard
## 🎯 User Roles & Features

| Role | Simple Mode | Trial Mode | Live Mode | Scheduler | Admin |
|------|-------------|------------|-----------|-----------|-------|
| Normal | ❌ | ✅ | ❌ | ❌ | ❌ |
| VIP I | ✅ | ✅ | ✅ | ❌ | ❌ |
| VIP II | ✅ | ✅ | ✅ | ✅ | ❌ |
| Premium | ✅ | ✅ | ✅ | ✅ | ❌ |
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |

## 🔐 Security & Privacy

- **Local Storage Only** - ข้อมูลเก็บในเครื่องเท่านั้น
- **AES-256 Encryption** - รหัสผ่านถูกเข้ารหัส
- **No Data Collection** - ไม่เก็บข้อมูลส่วนตัว
- **Secure Communication** - HTTPS เท่านั้น

## 🐛 Known Issues

- **Windows Defender** อาจบล็อกโปรแกรม → เพิ่ม Exclusion
- **Chrome Updates** อาจทำให้ต้องรีสตาร์ท → ปิด Auto Update
- **High DPI Displays** อาจแสดงผลไม่ชัด → ตั้งค่า Compatibility

## 🔄 Changelog

### v1.0.0 (2024-01-01)
- ✅ เพิ่ม Simple Mode สำหรับผู้เริ่มต้น
- ✅ ปรับปรุง Performance & Stability
- ✅ เพิ่ม Configuration Wizard
- ✅ เพิ่ม Comprehensive Documentation

### v0.9.0 (2023-12-15)
- ✅ เพิ่ม Smart Fallback System
- ✅ ปรับปรุง LINE Auto Login
- ✅ เพิ่ม Multi-Profile Support

## 🤝 Contributing

เรายินดีรับ Contribution! กรุณาอ่าน [CONTRIBUTING.md](CONTRIBUTING.md) ก่อน

## 📞 Support

### 🆘 Emergency (วันจอง)
- **LINE:** @newbies_emergency

### 💬 General Support
- **LINE:** @newbies_support
- **Email:** support@newbiesbot.com
- **Telegram:** @newbies_help
- **เวลาทำการ:** 9:00-18:00 น.


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Made with ❤️ by BokkChoY Company**
