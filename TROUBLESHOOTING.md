# 🔧 Newbies Bot - Troubleshooting Guide

## 🚨 ปัญหาเร่งด่วน

### โปรแกรมไม่เปิด / Crash ทันที
```
❌ ปัญหา: คลิก NewbiesBot.exe แล้วไม่มีอะไรเกิดขึ้น
```
**วิธีแก้:**
1. **คลิกขวา → Run as administrator**
2. ตรวจสอบ Windows Defender:
   - เปิด Windows Security
   - Virus & threat protection
   - Protection history
   - หาไฟล์ที่ถูกบล็อก → Restore
3. ติดตั้ง **Visual C++ Redistributable**:
   - ดาวน์โหลดจาก Microsoft
   - ติดตั้งทั้ง x86 และ x64

### เบราว์เซอร์เปิดไม่ได้
```
❌ ปัญหา: "ไม่สามารถเปิดเบราว์เซอร์ได้"
```
**วิธีแก้:**
1. **ปิด Chrome/Edge ทั้งหมด:**
   ```
   Task Manager → Processes → ฆ่า chrome.exe / msedge.exe ทั้งหมด
   ```
2. **เปลี่ยน Browser Profile:**
   - ใช้ "Default" แทน Profile อื่น
3. **รีสตาร์ทโปรแกรม**
4. **ตรวจสอบ Port:**
   ```bash
   netstat -an | findstr :9222
   # ถ้ามี Port ใช้งานอยู่ ให้ปิดโปรแกรมที่ใช้
   ```

### จองไม่สำเร็จ
```
❌ ปัญหา: "การจองล้มเหลว" / "ไม่พบปุ่ม"
```
**วิธีแก้:**
1. **ตรวจสอบเน็ต:**
   - ความเร็วต้อง > 10 Mbps
   - Ping < 100ms
2. **ปิด VPN/Proxy**
3. **ลองโหมดทดลองก่อน**
4. **เปลี่ยนการตั้งค่า:**
   - เพิ่ม Delay เป็น 1-2 วินาที
   - ลด Timer เป็น 3-5 วินาที

## 🐛 ปัญหาทั่วไป

### 1. การเข้าสู่ระบบ

#### "Username หรือ Password ไม่ถูกต้อง"
- ตรวจสอบ Caps Lock
- ลองพิมพ์ใน Notepad ก่อน
- ติดต่อ Admin เพื่อรีเซ็ตรหัส

#### "บัญชีหมดอายุแล้ว"
- ตรวจสอบวันหมดอายุ
- ติดต่อ Admin เพื่อต่ออายุ

#### "เชื่อมต่อไม่ได้"
- ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต
- ปิด Firewall ชั่วคราว
- ลองใช้ Hotspot มือถือ

### 2. LINE Auto Login

#### "ไม่พบ Password สำหรับ Email นี้"
1. ไปที่ Single Booking → ตั้งค่า LINE/Profile
2. แท็บ LINE → ใส่ Email/Password ใหม่
3. กด "บันทึก LINE"

#### "Login LINE ไม่สำเร็จ"
- ตรวจสอบ Email/Password ใน LINE App
- ลอง Login ด้วยตนเองใน Browser ก่อน
- ปิด 2FA ใน LINE (ชั่วคราว)

#### "รอยืนยันตัวตนในมือถือ"
1. เปิด LINE บนมือถือ
2. รอ Notification "ยืนยันการเข้าสู่ระบบ"
3. กด "ยืนยัน"
4. หากไม่มี Notification → รีสตาร์ท LINE App

### 3. การจอง

#### "ไม่พบสาขา/เวลา"
- ตรวจสอบว่าเปิดจองแล้วหรือยัง
- ลองรีเฟรชข้อมูล API
- เปลี่ยนไปสาขาอื่น

#### "ปุ่ม Register ไม่ Active"
- เพิ่ม Timer เป็น 10-15 วินาที
- ตรวจสอบว่าเลือกข้อมูลครบหรือไม่
- ลองกดด้วยตนเอง (เปิด Manual Mode)

#### "หน้าเว็บโหลดช้า"
- เพิ่ม Delay เป็น 2-3 วินาที
- ปิดแท็บอื่นใน Browser
- ปิดโปรแกรมอื่นที่ใช้เน็ต

### 4. Performance

#### "โปรแกรมช้า/แฮง"
- ปิดโปรแกรมอื่นที่ไม่จำเป็น
- เพิ่ม RAM (แนะนำ 8GB+)
- ใช้ SSD แทน HDD

#### "Browser ใช้ RAM เยอะ"
- ปิดแท็บที่ไม่ใช้
- ใช้ Profile แยกสำหรับจอง
- รีสตาร์ท Browser เป็นระยะ

## 🔍 การวินิจฉัยปัญหา

### ตรวจสอบ Log Files
```
ที่อยู่: logs/newbies_bot_YYYY-MM-DD.log

ข้อความสำคัญ:
- ERROR: ข้อผิดพลาดร้ายแรง
- WARNING: คำเตือน
- CRITICAL: ปัญหาที่ต้องแก้ด่วน
```

### ตรวจสอบการเชื่อมต่อ
```bash
# ทดสอบการเชื่อมต่อ Backend
ping backend-server.com

# ทดสอบ DNS
nslookup backend-server.com

# ทดสอบ Port
telnet backend-server.com 443
```

### ตรวจสอบ Browser
1. เปิด Chrome → F12 → Console
2. หาข้อความสีแดง (Error)
3. ถ่ายภาพหน้าจอส่งให้ Support

## 🛠️ วิธีแก้ปัญหาขั้นสูง

### รีเซ็ตการตั้งค่า
```bash
# ลบการตั้งค่าทั้งหมด
rmdir /s "%USERPROFILE%\.newbies_bot"

# รีสตาร์ทโปรแกรม → จะเข้า Configuration Wizard ใหม่
```

### ล้าง Browser Cache
```bash
# Chrome
rmdir /s "%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache"

# Edge
rmdir /s "%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache"
```

### แก้ไข Registry (ระวัง!)
```
เฉพาะผู้เชี่ยวชาญ:
HKEY_CURRENT_USER\Software\NewbiesBot\
- ลบ Key ทั้งหมด
- รีสตาร์ทโปรแกรม
```

### ใช้ Safe Mode
1. กด Shift + คลิกขวาที่ NewbiesBot.exe
2. เลือก "Open PowerShell window here"
3. พิมพ์: `.\NewbiesBot.exe --safe-mode`

## 🚨 ปัญหาเฉพาะ Windows

### Windows 11
- **ปัญหา:** SmartScreen บล็อกโปรแกรม
- **แก้:** คลิก "More info" → "Run anyway"

### Windows 10
- **ปัญหา:** .NET Framework เก่า
- **แก้:** อัปเดต Windows Update

### Windows Defender
```
การตั้งค่า Exclusion:
1. Windows Security
2. Virus & threat protection
3. Exclusions → Add folder
4. เลือกโฟลเดอร์ NewbiesBot
```

## 📊 การตรวจสอบประสิทธิภาพ

### System Requirements Check
```
RAM Usage: < 2GB (ปกติ)
CPU Usage: < 50% (ขณะจอง)
Disk Space: > 100MB ว่าง
Network: > 10 Mbps
```

### Browser Performance
```
Chrome Processes: < 10 (แนะนำ)
Memory per Tab: < 500MB
Extensions: ปิดที่ไม่จำเป็น
```

## 🔄 การกู้คืนข้อมูล

### สำรองข้อมูลสำคัญ
```bash
# การตั้งค่า
copy "%USERPROFILE%\.newbies_bot\wizard_config.json" "backup\"

# LINE Credentials
copy "%APPDATA%\BokkChoYCompany\line_data.json" "backup\"

# User Profiles
copy "%APPDATA%\BokkChoYCompany\user_profile.json" "backup\"
```

### กู้คืนข้อมูล
```bash
# คัดลอกไฟล์กลับ
copy "backup\*" "%USERPROFILE%\.newbies_bot\"
copy "backup\*" "%APPDATA%\BokkChoYCompany\"
```

## 📞 การขอความช่วยเหลือ

### ข้อมูลที่ต้องส่งให้ Support

#### ข้อมูลระบบ
```
- Windows Version: (Win+R → winver)
- RAM: (Task Manager → Performance)
- Browser Version: (chrome://version)
- Program Version: (ดูใน About)
```

#### ข้อมูลปัญหา
```
- เวลาที่เกิดปัญหา
- ขั้นตอนที่ทำก่อนเกิดปัญหา
- ข้อความ Error (ถ่ายภาพหน้าจอ)
- ไฟล์ Log (ล่าสุด)
```

#### วิธีส่ง Log
1. เปิด `logs/` folder
2. หาไฟล์วันที่เกิดปัญหา
3. คลิกขวา → Send to → Compressed folder
4. ส่งไฟล์ .zip ให้ Support

### ช่องทางติดต่อ
- **LINE:** @newbies_support
- **Email:** support@newbiesbot.com
- **Telegram:** @newbies_help
- **เวลาทำการ:** 9:00-18:00 น.

### Emergency Contact
หากเป็นปัญหาเร่งด่วน (เช่น วันจอง):
- **LINE:** @newbies_emergency
- **Phone:** 02-xxx-xxxx
- **เวลา:** 24/7

## ✅ Checklist การแก้ปัญหา

เมื่อเกิดปัญหา ให้ทำตามลำดับ:

- [ ] รีสตาร์ทโปรแกรม
- [ ] รีสตาร์ท Browser
- [ ] ตรวจสอบการเชื่อมต่อเน็ต
- [ ] ดู Log Files
- [ ] ลองโหมดทดลอง
- [ ] ปิด VPN/Firewall
- [ ] รีสตาร์ทคอมพิวเตอร์
- [ ] ติดต่อ Support (ถ้าแก้ไม่ได้)

## 🎯 FAQ - คำถามที่พบบ่อย

**Q: ทำไมจองไม่ได้บางครั้ง?**
A: อาจเป็นเพราะเน็ตช้า, เซิร์ฟเวอร์เต็ม, หรือการตั้งค่าไม่เหมาะสม

**Q: LINE OTP ไม่มาทำไง?**
A: ตรวจสอบ LINE App, เปิด Notification, หรือลอง Login ด้วยตนเอง

**Q: โปรแกรมใช้ RAM เยอะไหม?**
A: ปกติใช้ 200-500MB, ถ้าเกิน 1GB ให้รีสตาร์ท

**Q: สามารถใช้หลาย Account ได้ไหม?**
A: ได้ แต่ต้องใช้ Browser Profile แยกกัน

**Q: ข้อมูลปลอดภัยไหม?**
A: ปลอดภัย เก็บในเครื่องเท่านั้น มีการเข้ารหัส