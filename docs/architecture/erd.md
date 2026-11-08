# ERD — Smart Restaurant Stock & Mini-POS

สร้างจาก `models.py` ของ 5 apps (`accounts`, `inventory`, `menus`, `orders`, `analytics`)
ที่ `main` @ `7419efe` ตารางที่ Django สร้างให้เอง (`auth_group`, `django_session` ฯลฯ) ไม่ได้ใส่ไว้

```mermaid
erDiagram
    Restaurant ||--o{ CustomUser : "staff_members"
    Restaurant ||--o{ Ingredient : "ingredients"
    Restaurant ||--o{ StockIn : "stock_ins"
    Restaurant ||--o{ MenuItem : owns
    Restaurant ||--o{ Order : "orders"
    Restaurant ||--o{ AIInsight : "ai_insights"

    Ingredient ||--o{ StockIn : "lots"
    MenuItem ||--o{ RecipeItem : "BOM"
    Ingredient |o--o{ RecipeItem : "used_in (SET_NULL)"

    Order ||--o{ OrderItem : "items"
    MenuItem |o--o{ OrderItem : "sold_as (PROTECT)"
    OrderItem ||--o{ StockDeduction : "stock_deductions"
    Ingredient ||--o{ StockDeduction : "deducted (PROTECT)"
    StockIn |o--o{ StockDeduction : "from_lot (PROTECT)"

    CustomUser |o--o{ Order : "created_by (SET_NULL)"
    CustomUser |o--o{ StockIn : "received_by (SET_NULL)"

    Restaurant {
        int id PK
        string name
        string address
        datetime created_at
    }
    CustomUser {
        int id PK
        int restaurant_id FK "nullable"
        string role "owner | staff"
        string username
    }
    Ingredient {
        int id PK
        int restaurant_id FK
        string name "unique ต่อร้าน (ไม่สนตัวพิมพ์)"
        string barcode "unique ต่อร้าน (ยกเว้นว่าง)"
        string unit
        decimal stock_quantity
        decimal par_level
        decimal price "CHECK price > 0"
        int revision
    }
    StockIn {
        int id PK
        int restaurant_id FK
        int ingredient_id FK
        string lot_code "unique ต่อร้าน (ยกเว้นว่าง)"
        decimal quantity
        decimal remaining_quantity
        date expiry_date "nullable"
        int received_by_id FK "nullable"
        datetime received_at
    }
    MenuItem {
        int id PK
        int restaurant_id FK
        string name
        string normalized_name "unique ต่อร้าน"
        decimal price "CHECK price > 0"
        bool is_active
        int revision
    }
    RecipeItem {
        int id PK
        int menu_item_id FK
        int ingredient_id FK "nullable"
        decimal quantity_used "CHECK > 0"
        string ingredient_name_snapshot
        string ingredient_unit_snapshot
    }
    Order {
        int id PK
        int restaurant_id FK
        int created_by_id FK "nullable"
        decimal total_amount
        string status "completed | cancelled"
        datetime created_at
    }
    OrderItem {
        int id PK
        int order_id FK
        int menu_item_id FK "nullable"
        string name_snapshot
        decimal unit_price
        int quantity
        decimal line_total
    }
    StockDeduction {
        int id PK
        int order_item_id FK
        int ingredient_id FK
        int lot_id FK "nullable"
        decimal quantity
    }
    AIInsight {
        int id PK
        int restaurant_id FK
        text content
        string provider "rules | openai"
        datetime generated_at
    }
```

## จุดออกแบบที่ควรรู้

| จุด | เหตุผล |
|---|---|
| ทุกตารางธุรกิจมี `restaurant_id` (ยกเว้นลูกที่ผ่านพ่อ เช่น `OrderItem`, `RecipeItem`, `StockDeduction`) | แยกข้อมูลต่อร้าน (multi-tenant) |
| `OrderItem.name_snapshot`, `unit_price` และ `RecipeItem.ingredient_*_snapshot` | เก็บค่า ณ ตอนขาย/ตอนทำสูตร ข้อมูลเก่าไม่เพี้ยนเมื่อแก้ชื่อหรือราคาทีหลัง |
| `StockDeduction` ผูกกับ `StockIn` (ล็อต) | ตรวจย้อนได้ว่าขายแต่ละจานตัดจากล็อตไหน (FEFO ตาม ADR 002) |
| `RecipeItem.ingredient` เป็น `SET_NULL` | ลบวัตถุดิบได้โดยสูตรเก่ายังเก็บชื่อจาก snapshot |
| `OrderItem.menu_item`, `StockDeduction.*` เป็น `PROTECT` | กันลบเมนู/วัตถุดิบ/ล็อตที่มีประวัติขายอ้างอิงอยู่ |
| `Ingredient.revision`, `MenuItem.revision` | optimistic locking กันแก้ทับกัน |
| `Ingredient.stock_quantity` | ยอดรวมของวัตถุดิบ ส่วนวันหมดอายุเก็บรายล็อตใน `StockIn` |

เอกสารที่เกี่ยวข้อง: [C4](c4.md), [ADR 002 FEFO](../adr/002-fefo-lot-allocation.md)
