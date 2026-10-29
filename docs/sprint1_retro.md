# รายงานการประชุมทบทวนรอบการทำงาน (Sprint 1 Retrospective)
## วิชา CN331 Software Engineering | กลุ่ม หมูแองกี้เบิ้ด

> **Sprint 2 Goal:**  
> *"ส่งมอบ Mini-POS ที่ตัดสต็อกแบบ atomic พร้อมแดชบอร์ด AI Insights โดยโค้ดอยู่บน Service Layer และทุก PR ผ่าน CI (เทส, lint, coverage ≥ 80%)"*

---

## 1. การประเมินความเร็วในการทำงาน (Velocity Assessment)

ใน Sprint 1 ทีมได้วางแผนงานตามเอกสาร Team Work Division ไว้ทั้งหมด 5 User Stories รวม 25 Story Points:

| User Story | คำอธิบาย | ผู้รับผิดชอบ | แต้มที่วางแผน | สถานะจริงใน Sprint 1 | Pull Request |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **US-01** | Auth, Tenant & Layout | วรเมธ | 5 | **Done** | PR #7 |
| **US-02** | Inventory & Inbound Stock | ณฤดี | 5 | **Done** | PR #8 |
| **US-03** | Menu Management & Recipe BOM | ธีภพ | 5 | **Done** | PR #16 |
| **US-04** | Mini-POS & Stock Deduction | ตุลธร | 5 | *Moved to Sprint 2* | — |
| **US-05** | AI Analytics Dashboard | วชิรวิทย์ | 5 | *Moved to Sprint 2* | — |
| **รวม** | | | **25 SP** | **สำเร็จจริง: 15 SP** | |

### สรุปตัวเลข Velocity:
* **Planned Velocity:** 25 Story Points
* **Actual Velocity:** **15 Story Points** (คิดเป็น 60% ของที่วางแผนไว้)
* **ข้อสังเกต:** การประเมินขนาดงานใน Sprint 1 มีการมองโลกในแง่ดีเกินไป (Optimism Bias) และมี Technical Debt จากการเขียน Business Logic ซับซ้อนใน View ทำให้ใช้เวลาในการรีวิวและแก้โค้ดนานกว่าที่คาดการณ์

---

## 2. การวิเคราะห์ผลการทำงาน (Retro Matrix)

### 👍 สิ่งที่เป็นไปด้วยดี (What Went Well)
1. **การแยกข้อมูลร้านค้า (Multi-Tenant Isolation):** สามารถควบคุมสิทธิ์และการแยกข้อมูลวัตถุดิบและเมนูของแต่ละร้านค้าได้อย่างสมบูรณ์ ปราศจาก Data Leakage ข้ามร้าน
2. **ระบบผูกสูตรอาหาร (Recipe BOM Builder):** ฟังก์ชันคำนวณต้นทุนต่อจานและ Snapshot ราคาทำงานได้แม่นยำและมีเสถียรภาพ
3. **การเขียน Unit Tests:** ทีมมีการเขียน Unit Test ครอบคลุมการทำงาน ทำให้ Code Coverage ใน Sprint 1 สูงกว่าเกณฑ์ขั้นต่ำ (อยู่ที่ 93.56%)

### 👎 สิ่งที่ยังไม่ราบรื่นและต้องปรับปรุง (What Didn't Go Well)
1. **Fat Views ใน App `inventory`:** โค้ดใน `inventory/views.py` มีความยาวเกินกว่า 300 บรรทัด มีการคำนวณและตัดสต็อกปะปนใน View ทำให้อ่านยากและเสี่ยงต่อ Concurrency Bug
2. **Pull Request ค้างการรีวิวนาน:** การตรวจโค้ด (Peer Code Review) ล่าช้า ทำให้เกิดคอขวดก่อนจะรวมโค้ดเข้าสู่ `main`
3. **ขาดระบบตรวจ Linter & Security อัตโนมัติ:** ใน Sprint 1 ยังไม่มีการตั้งค่า `black`, `flake8`, และ `bandit` บน GitHub Actions ทำให้สไตล์โค้ดของแต่ละคนแตกต่างกัน

---

## 3. แผนการปรับปรุงสำหรับ Sprint 2 (Action Items)

1. **ปรับสถาปัตยกรรมเป็น Service Layer:** เริ่มใช้ `services.py` (Write logic) และ `selectors.py` (Read logic) ทันทีใน App ใหม่ (`orders`, `analytics`) และทำการ Refactor App เก่า (`inventory`) ตามข้อตกลง ADR 001
2. **ติดตั้ง CI Pipeline และ Quality Gates:** นำ `black`, `flake8`, `bandit` และเกณฑ์ Test Coverage ≥ 80% มาเป็นด่านตรวจอัตโนมัติบน GitHub Actions
3. **กฎการตรวจ Code Review ภายใน 24 ชม.:** สมาชิกทุกคนต้องเข้าตรวจและให้ Feedback บน PR ของคู่ตรวจตนเองภายใน 24 ชั่วโมง เพื่อไม่ให้งานคั่งค้าง
4. **จัดสรรโควตา Technical Debt ≥ 20%:** ใน Sprint 2 จะไม่รับงานฟีเจอร์เกินกำลัง และกันโควตาแต้มไว้จัดการระบบและ Refactor อย่างน้อย 20%

---

## 4. แผนงาน Sprint 2 Backlog (ตาม Actual Velocity)

เพื่อไม่ให้งานล้นมือ ทีมปรับขนาดงานใน Sprint 2 ให้ใกล้เคียงกับ Actual Velocity ของ Sprint 1 (15 SP) โดยวางแผนไว้ที่ **16 Story Points**:

| ประเภทงาน | รหัสงาน | รายละเอียดงาน | ผู้รับผิดชอบ | Story Points |
| :---: | :---: | :--- | :---: | :---: |
| **Feature** | **US-04** | Mini-POS Order Checkout & Out-of-Stock Guard | ตุลธร | 5 |
| **Feature** | **US-05** | AI Analytics Dashboard with Google Gemini | วชิรวิทย์ | 5 |
| **Tech Debt** | **TD-01** | Refactor `inventory` เป็น Service Layer + ADR | ณฤดี | 4 |
| **Tech Debt** | **TD-02** | CI Pipeline & Quality Gates (Black, Flake8, Bandit) | ทีมกลาง | 2 |
| **รวมทั้งสิ้น** | | | | **16 SP** |

> **สัดส่วน Technical Debt:** 6 จาก 16 แต้ม = **37.5%** (ผ่านเกณฑ์ที่อาจารย์แนะนำ ≥ 20%)
