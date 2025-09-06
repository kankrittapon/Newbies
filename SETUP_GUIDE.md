# 🛠️ Newbies Bot - Setup Guide

## 📋 ความต้องการระบบ

### ระบบปฏิบัติการ
- **Windows 10** (64-bit) หรือใหม่กว่า
- **Windows 11** (แนะนำ)

### ฮาร์ดแวร์
- **RAM:** 4 GB ขึ้นไป (แนะนำ 8 GB)
- **Storage:** 500 MB พื้นที่ว่าง
- **CPU:** Intel/AMD ใดๆ (รองรับ x64)
- **Internet:** ความเร็ว 10 Mbps ขึ้นไป

### ซอฟต์แวร์
- **Google Chrome** หรือ **Microsoft Edge** (เวอร์ชันล่าสุด)
- **Microsoft Visual C++ Redistributable** (มักติดตั้งอยู่แล้ว)

## 📥 การติดตั้ง

### วิธีที่ 1: ใช้ Executable (แนะนำ)
1. ดาวน์โหลด `NewbiesBot.exe`
2. วางไฟล์ในโฟลเดอร์ที่ต้องการ
3. คลิกขวา → **Run as administrator** (ครั้งแรก)
4. ทำตามขั้นตอนใน Configuration Wizard

### วิธีที่ 2: Build จาก Source Code
```bash
# 1. Clone repository
git clone https://github.com/your-repo/newbies-bot.git
cd newbies-bot

# 2. ติดตั้ง dependencies
pip install -r requirements.txt

# 3. Build executable
build.bat

# 4. รันโปรแกรม
NewbiesBot.exe
```

## 🧙♂️ Configuration Wizard

### ขั้นตอนที่ 1: ยินดีต้อนรับ
- อ่านข้อมูลเบื้องต้น
- กด "ถัดไป →"

### ขั้นตอนที่ 2: ข้อมูลผู้ใช้
```
Username: [ใส่ username ของคุณ]
Password: [ใส่ password ของคุณ]
☑️ จำรหัสผ่าน (Auto Login)
```

### ขั้นตอนที่ 3: ตั้งค่า LINE
```
LINE Email: [ใส่ email ที่ใช้กับ LINE]
LINE Password: [ใส่รหัสผ่าน LINE]
☑️ เปิดใช้ LINE Auto Login
```
**หมายเหตุ:** ข้อมูล LINE จะใช้สำหรับ Auto Login เท่านั้น

### ขั้นตอนที่ 4: ตั้งค่าโปรไฟล์
```
ชื่อ: [ชื่อจริง]
นามสกุล: [นามสกุลจริง]
เพศ: [ชาย/หญิง]
เลขบัตรประชาชน: [13 หลัก]
เบอร์โทร: [เบอร์โทรศัพท์]
```

### ขั้นตอนที่ 5: ตั้งค่าเบราว์เซอร์
```
เบราว์เซอร์หลัก:
○ 🔵 Google Chrome (แนะนำ)
○ 🔷 Microsoft Edge

Profile:
○ 📁 Default (แนะนำ)
○ 📁 Profile 1
○ 📁 Profile 2
○ 📁 Profile 3

☑️ ปิดเบราว์เซอร์อัตโนมัติหลังจองเสร็จ
```

### ขั้นตอนที่ 6: เสร็จสิ้น
- ตรวจสอบสรุปการตั้งค่า
- กด "เสร็จสิ้น"

## 🔧 การตั้งค่าเพิ่มเติม

### ตั้งค่า Chrome Profiles
1. เปิด Chrome
2. คลิกรูปโปรไฟล์มุมขวาบน
3. เลือก "Add" → สร้าง Profile ใหม่
4. ตั้งชื่อ เช่น "Booking Profile"
5. ใช้ Profile นี้ในโปรแกรม

### ตั้งค่า Windows Defender
เพิ่ม Exclusion เพื่อป้องกันการสแกน:
1. เปิด **Windows Security**
2. **Virus & threat protection**
3. **Manage settings** (under Virus & threat protection settings)
4. **Add or remove exclusions**
5. **Add an exclusion** → **Folder**
6. เลือกโฟลเดอร์ที่มี `NewbiesBot.exe`

### ตั้งค่า Firewall
หากมี Firewall บล็อก:
1. เปิด **Windows Defender Firewall**
2. **Allow an app or feature through Windows Defender Firewall**
3. **Change settings** → **Allow another app**
4. เลือก `NewbiesBot.exe`
5. เลือก **Private** และ **Public**

## 🌐 การตั้งค่าเบราว์เซอร์

### Google Chrome
```bash
# เปิด Chrome ด้วย Remote Debugging
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\ChromeProfile"
```

### Microsoft Edge
```bash
# เปิด Edge ด้วย Remote Debugging
msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\EdgeProfile"
```

**หมายเหตุ:** โปรแกรมจะจัดการเรื่องนี้อัตโนมัติ

## 📁 โครงสร้างไฟล์

```
NewbiesBot/
├── NewbiesBot.exe          # โปรแกรมหลัก
├── logs/                   # Log files
│   └── newbies_bot_2024-01-01.log
├── assets/                 # ไฟล์เสริม (ถ้ามี)
│   └── icon.ico
└── config/                 # การตั้งค่า (สร้างอัตโนมัติ)
    ├── user_config.json
    └── browser_profiles.json

# ไฟล์ผู้ใช้ (ใน %USERPROFILE%)
%USERPROFILE%/.newbies_bot/
├── wizard_config.json      # การตั้งค่าจาก Wizard
├── wizard_completed        # Marker file
└── logs/                   # User logs
```

## 🔐 การตั้งค่าความปลอดภัย

### การเข้ารหัสข้อมูล
- รหัสผ่านถูกเข้ารหัสด้วย AES-256
- ข้อมูลส่วนตัวเก็บใน Local Storage เท่านั้น
- ไม่มีการส่งข้อมูลไปเซิร์ฟเวอร์ภายนอก

### การสำรองข้อมูล
```bash
# สำรองการตั้งค่า
copy "%USERPROFILE%\.newbies_bot\*" "D:\Backup\NewbiesBot\"

# กู้คืนการตั้งค่า
copy "D:\Backup\NewbiesBot\*" "%USERPROFILE%\.newbies_bot\"
```

## 🚀 การอัปเดต

### อัปเดตอัตโนมัติ
- โปรแกรมจะตรวจสอบอัปเดตเมื่อเปิด
- แจ้งเตือนเมื่อมีเวอร์ชันใหม่

### อัปเดตด้วยตนเอง
1. ดาวน์โหลด `NewbiesBot.exe` เวอร์ชันใหม่
2. ปิดโปรแกรมเก่า
3. แทนที่ไฟล์เก่าด้วยไฟล์ใหม่
4. เปิดโปรแกรม (การตั้งค่าจะยังอยู่)

## 🔧 การแก้ไขปัญหาเบื้องต้น

### โปรแกรมเปิดไม่ได้
1. คลิกขวา → **Run as administrator**
2. ตรวจสอบ Windows Defender
3. ติดตั้ง Visual C++ Redistributable

### เบราว์เซอร์เปิดไม่ได้
1. ปิด Chrome/Edge ทั้งหมด
2. รีสตาร์ทโปรแกรม
3. เปลี่ยน Browser Profile

### จองไม่สำเร็จ
1. ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต
2. ปิด VPN (ถ้ามี)
3. ลองใช้โหมดทดลองก่อน

## 📞 การขอความช่วยเหลือ

### ข้อมูลที่ต้องเตรียม
- เวอร์ชันโปรแกรม
- ระบบปฏิบัติการ
- ขั้นตอนที่เกิดปัญหา
- ข้อความ Error (ถ้ามี)
- ไฟล์ Log (ใน `logs/` folder)

### ช่องทางติดต่อ
- **LINE:** @newbies_support
- **Email:** support@newbiesbot.com
- **GitHub Issues:** (สำหรับ Technical Issues)

## ✅ Checklist หลังติดตั้ง

- [ ] โปรแกรมเปิดได้ปกติ
- [ ] ผ่าน Configuration Wizard แล้ว
- [ ] ทดสอบเปิด Chrome/Edge ได้
- [ ] ทดสอบโหมดทดลองได้
- [ ] ตั้งค่า LINE Auto Login แล้ว (ถ้าต้องการ)
- [ ] สำรองการตั้งค่าแล้ว
- [ ] อ่าน User Manual แล้ว