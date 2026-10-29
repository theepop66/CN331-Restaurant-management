# ADR 002: FEFO Lot Deduction Strategy for Inventory and POS

* **Status:** Accepted
* **Date:** 2026-10-28
* **Deciders:** ทีมหมูแองกี้เบิ้ด (CN331 Software Engineering)
* **Consulted:** ข้อกำหนดระบบร้านอาหาร US-02 (Inbound Stock), US-04 (Mini-POS), และเป้าหมายลด Food Waste

---

## 1. Context and Problem Statement (บริบทและปัญหา)

ในระบบจัดการร้านอาหาร วัตถุดิบแต่ละล็อตที่รับเข้าคลัง (`StockIn`) มีวันหมดอายุ (`expiry_date`) และเวลาที่รับของ (`received_at`) บันทึกไว้:
* หากใช้กลยุทธ์ **FIFO (First-In, First-Out)** แบบดั้งเดิม ระบบจะตัดล็อตที่รับเข้ามาก่อนเสมอ โดยไม่สนใจวันหมดอายุจริง
* ในธุรกิจร้านอาหาร ความเป็นจริงอาจมีการรับวัตถุดิบล็อตใหม่เข้ามา แต่วันหมดอายุสั้นกว่าล็อตเดิม (เช่น นมสด หรือเนื้อสัตว์ที่ซื้อคนละผู้ผลิต)
* หากไม่นำวันหมดอายุมาคำนวณ วัตถุดิบที่หมดอายุก่อนจะตกค้างอยู่ในคลังและเน่าเสีย เกิดเป็น **Food Waste** และสูญเสียต้นทุนโดยเปล่าประโยชน์

---

## 2. Decision (การตัดสินใจ)

ทีมตัดสินใจใช้กลยุทธ์ **FEFO (First-Expired, First-Out: หมดอายุก่อน ออกก่อน)** ในการตัดล็อตวัตถุดิบเมื่อมีการขายผ่าน Mini-POS (US-04):

### 2.1 ลำดับการจัดสรรล็อต (Sorting Priority)
เมื่อเกิดคำสั่งซื้อ ระบบจะค้นหาล็อตสินค้าในโมเดล `StockIn` ของวัตถุดิบนั้นๆ ที่ยังมี `remaining_quantity > 0` และเรียงลำดับด้วยเงื่อนไข:
1. **`expiry_date ASC (Nulls Last)`:** ล็อตที่มีวันหมดอายุระบุไว้และหมดอายุก่อน จะถูกนำมาตัดยอดก่อนเป็นอันดับแรก ล็อตที่ไม่ระบุวันหมดอายุจะถูกจัดไว้ท้ายสุด
2. **`received_at ASC` (Tie-breaker 1):** หากวันหมดอายุเท่ากัน ให้ตัดล็อตที่รับเข้ามาในระบบก่อน
3. **`id ASC` (Tie-breaker 2):** ลำดับ Primary Key ตามฐานข้อมูล

คำสั่งใน Django ORM:
```python
StockIn.objects.filter(
    restaurant_id=restaurant.pk,
    ingredient_id=ing_id,
    remaining_quantity__gt=0,
).order_by(
    F('expiry_date').asc(nulls_last=True),
    'received_at',
    'id',
)
```

### 2.2 การบันทึก Audit Trail
เพื่อความโปร่งใสและตรวจสอบย้อนหลังได้ ทุกครั้งที่มีการตัดล็อต ระบบจะสร้างเรคคอร์ดในโมเดล `StockDeduction` ผูกกับ `OrderItem`, `Ingredient`, `StockIn` (ล็อตที่ถูกตัด) และปริมาณที่หักออก

---

## 3. Consequences (ผลกระทบและผลลัพธ์)

### ข้อดี (Positive Consequences):
* ลดอัตราการเน่าเสียของวัตถุดิบในร้านอาหาร (Food Waste Reduction) อย่างมีนัยสำคัญ
* ข้อมูลในคลังตรงกับหลักปฏิบัติสากลของการบริหารสต็อกอาหารสด (Food Safety Best Practices)
* มี Audit Trail ให้เจ้าของร้านตรวจสอบได้ว่าเมนูใดใช้ของจากล็อตไหน

### ข้อเสีย / ข้อจำกัด (Trade-offs):
* การจัดสรรล็อตต้องอ่านข้อมูล `StockIn` หลายแถวและอัปเดตแบบวนซ้ำ (Iterative Deduction) จึงต้องอยู่ภายใต้ `restaurant_transaction` เสมอเพื่อรักษา Data Consistency
