# Smart Restaurant Stock & Mini-POS System

> **กลุ่ม:** หมูแองกี้เบิ้ด  
> **วิชา:** CN331 Software Engineering (วิศวกรรมซอฟต์แวร์)  
> **ภาคการศึกษา:** 1/2569  
> **ภาควิชา:** วิศวกรรมไฟฟ้าและคอมพิวเตอร์ คณะวิศวกรรมศาสตร์ มหาวิทยาลัยธรรมศาสตร์ (TSE)

---

## 1. เกี่ยวกับโครงงาน (About the Project)

**Smart Restaurant Stock & Mini-POS System** เป็นเว็บแอปพลิเคชันสำหรับบริหารจัดการคลังวัตถุดิบและระบบขายหน้าร้าน (Point of Sale) แบบครบวงจรสำหรับธุรกิจร้านอาหาร เพื่อแก้ปัญหาต้นทุนวัตถุดิบรั่วไหล ของหมดสต็อกโดยไม่รู้ตัว และการสูญเสียจากวัตถุดิบเน่าเสีย/หมดอายุ

### จุดเด่นและฟังก์ชันหลักของระบบ (Key Features)
1. **ระบบคลังวัตถุดิบ (Smart Inventory Management):**
   * บันทึกรายการวัตถุดิบ หน่วยนับ ราคาต่อหน่วย วันหมดอายุ และจุดสั่งซื้อซ้ำ (`par_level`)
   * ระบบรับของเข้าคลัง (Stock Receiving) บันทึกยอดเพิ่มอัตโนมัติ
2. **ระบบสูตรอาหารและคำนวณต้นทุน (Recipe / Bill of Materials - BOM):**
   * ผูกเมนูอาหารแต่ละจานเข้ากับวัตถุดิบและสัดส่วนที่ใช้จริง
   * คำนวณต้นทุนวัตถุดิบต่อจาน (Cost per Dish) แบบไดนามิกทันที
3. **ระบบขายหน้าร้านและตัดสต็อกอัตโนมัติ (Mini-POS & Auto Stock Deduction):**
   * หน้าจอสำหรับพนักงานกดเลือกเมนูสั่งขายหน้าร้าน
   * หักลดสต็อกวัตถุดิบตามสูตรอาหารอัตโนมัติทันทีที่จบการขาย โดยใช้ Atomic Transaction เพื่อป้องกัน Race Condition
4. **ระบบแจ้งเตือนและแดชบอร์ดสรุปผล (Stock Alerts & Analytics):**
   * แจ้งเตือนวัตถุดิบใกล้หมดสต็อก (`current_stock <= par_level`)
   * แจ้งเตือนวัตถุดิบใกล้หมดอายุ (Shelf Life Alert)
   * หน้า Dashboard แสดงสถิติและภาพรวมต้นทุน
5. **ระบบยืนยันตัวตนและการแยกข้อมูล (Auth & Multi-Tenant):**
   * ระบบสมาชิกและกำหนดสิทธิ์ผู้ใช้ (`CustomUser`)
   * แยกข้อมูลวัตถุดิบและเมนูของแต่ละร้านออกจากกันโดยเด็ดขาด (Data Isolation)

---

## 2. วิธีการติดตั้งและรันระบบ (Getting Started & How to Run)

### ขั้นตอนการรัน (Step-by-Step Guide)

#### 1. Clone Repository (กรณีดึงลงเครื่องใหม่)
```bash
git clone https://github.com/theepop66/CN331-Restaurant-management.git
cd CN331-Restaurant-management
```

#### 2. สร้างและเปิดใช้งาน Virtual Environment

* **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

* **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  venv\Scripts\Activate.ps1
  ```

* **Windows (Command Prompt):**
  ```cmd
  python -m venv venv
  venv\Scripts\activate.bat
  ```

#### 3. ติดตั้ง Dependencies
```bash
pip install -r main/requirements.txt
```

#### 4. สั่ง Migrate ฐานข้อมูล
เข้าไปยังโฟลเดอร์ที่มีไฟล์ `manage.py`:
```bash
cd main/myproject
python manage.py migrate
```

#### 5. สร้างบัญชีผู้ดูแลระบบ (Superuser) — *ทำเฉพาะครั้งแรก*
```bash
python manage.py createsuperuser
```
*(กรอก Username, Email และ Password ตามคำแนะนำบนหน้าจอ)*

#### 6. เริ่มการทำงานของ Server (Run Server)
```bash
python manage.py runserver
```

#### 7. เข้าใช้งานระบบ
* **หน้าเว็บหลัก:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **หน้า Django Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## 3. สมาชิกกลุ่ม (Team Members)

| ลำดับ | รหัสนักศึกษา | ชื่อ - นามสกุล |
| :---: | :---: | :--- |
| 1 | 6710615094 | ณฤดี เธียรชูบุญ |
| 2 | 6710685014 | ธีภพ รัตนทรัพย์ศิริ |
| 3 | 6710615110 | ตุลธร ปานดำรง |
| 4 | 6710615268 | วรเมธ เผ่าสังข์ |
| 5 | 6710615250 | วชิรวิทย์ พุ่มหนู |