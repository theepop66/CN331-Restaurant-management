# ADR 001: Service Layer Architecture and Concurrency Control

* **Status:** Accepted
* **Date:** 2026-10-28
* **Deciders:** ทีมหมูแองกี้เบิ้ด (CN331 Software Engineering)
* **Consulted:** อาจารย์และข้อกำหนดวิชา CN331 Week 10 (Lab 2) & Week 11

---

## 1. Context and Problem Statement (บริบทและปัญหา)

ใน Sprint 1 การเขียนโค้ดของระบบร้านอาหารมี Business Logic จำนวนมากกระจุกตัวอยู่ภายใน Controller / View (เช่น ใน `inventory/views.py` มีฟังก์ชันคำนวณและตัดสต็อกใน View กว่า 300 บรรทัด) ซึ่งส่งผลเสีย:
1. **Fat Views / Low Cohesion:** View ทำหน้าที่มากเกินไป ทั้งรับ HTTP Request, ตรวจสอบสิทธิ์, คำนวณสต็อก, และ Render Template ทำให้ Unit Test ทำได้ยาก
2. **Race Conditions & Concurrency:** เมื่อมีการสั่งซื้อหรือเติมสต็อกพร้อมกัน (Concurrent Requests) การอ่านค่ายอดสต็อกมาคำนวณใน Python แล้วบันทึกกลับลงฐานข้อมูล อาจทำให้เกิดปัญหา Overwrite ยอดคงเหลือ หรือสต็อกติดลบ
3. **Database Portability:** ในช่วง Development ทีมใช้งาน **SQLite** ซึ่งเป็น File-level lock และไม่รองรับ Row-level locking (`select_for_update()` เป็น no-op บน SQLite) แต่ใน Production (Sprint 3) จะ Deploy บน **PostgreSQL** ผ่าน Render

---

## 2. Decision (การตัดสินใจทางสถาปัตยกรรม)

ทีมตัดสินใจนำแบบแผนสถาปัตยกรรม **Modular Monolith with Service Layer** มาใช้งาน:

### 2.1 แยกโค้ดเป็น Service Layer และ Selector Layer
* **`services.py` (Write Operations):**
  * รวบรวม Business Logic ที่มีการเปลี่ยนแปลงข้อมูล (Create, Update, Delete)
  * ฟังก์ชันใน Service ต้องไม่รับออบเจกต์ `HttpRequest` โดยตรง (รับเฉพาะ Clean Arguments หรือ Dataclass)
  * ครอบฟังก์ชันด้วย Database Transaction เสมอ
* **`selectors.py` (Read-only Queries):**
  * รวบรวม Query ที่ซับซ้อนและการดึงข้อมูลเพื่อแสดงผล
  * ปราศจาก Side Effects (ห้ามมีการแก้ไขหรือลบข้อมูลเด็ดขาด)
* **`views.py` (Thin Controllers):**
  * ทำหน้าที่เฉพาะแปลง HTTP Request -> เรียก Service / Selector -> ส่ง HTTP Response หรือ Redirect (PRG Pattern) ความยาวของแต่ละ View ไม่ควรเกิน 50 บรรทัด

### 2.2 กลไกควบคุม Concurrency (SQLite & PostgreSQL Compatible)
1. **Serialization Lock:** ใช้ context manager `restaurant_transaction(restaurant_id)` (ใน `accounts/transactions.py`) ซึ่งรัน conditional dummy UPDATE บนแถว `Restaurant` เพื่อดึง Write Lock ในระดับ SQLite และ Serialize แถวของร้านใน PostgreSQL
2. **Atomic F() Expressions:** ปรับปรุงยอดสต็อกด้วยคำสั่งระดับฐานข้อมูล เช่น:
   ```python
   Ingredient.objects.filter(pk=ing_id, stock_quantity__gte=needed).update(
       stock_quantity=F('stock_quantity') - needed
   )
   ```
   และตรวจสอบจำนวนแถวที่ถูกอัปเดต (`rows_updated == 0` แปลว่าสต็อกไม่พอหรือมีคำสั่งซื้ออื่นตัดไปก่อนหน้า)
3. **Pessimistic Locking บน PostgreSQL:** ใน Sprint 3 เมื่อย้ายไปรันบน PostgreSQL จะเปิดใช้งาน `select_for_update()` สำหรับการดึงล็อตสินค้าที่ต้องเรียงลำดับ

---

## 3. Consequences (ผลกระทบและผลลัพธ์)

### ข้อดี (Positive Consequences):
* **High Testability:** สามารถเขียน Unit Test ทดสอบ Business Logic ใน `services.py` และ `selectors.py` ได้โดยตรง ไม่ต้องผ่าน Client Request
* **High Concurrency Safety:** ป้องกันสต็อกติดลบได้ 100% ทั้งบน SQLite (ทดสอบผ่าน `test_concurrency.py`) และ PostgreSQL
* **Maintainability:** โค้ดแต่ละ App มีโครงสร้างเป็นระเบียบชัดเจน ง่ายต่อการส่งต่องานใน Sprint 2 และ Sprint 3

### ข้อเสีย / สิ่งที่ต้องแลก (Negative Consequences / Trade-offs):
* มีจำนวนไฟล์เพิ่มขึ้นในแต่ละ App (`services.py`, `selectors.py`)
* ต้องระมัดระวังไม่ให้เกิด Circular Import ระหว่าง App (ห้าม import ข้ามไปมาโดยไม่จำเป็น)
