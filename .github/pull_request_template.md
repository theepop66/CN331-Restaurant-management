## Related Issue
<!-- ระบุ Issue ที่เกี่ยวข้อง เช่น Closes #5 -->
Closes #

## Summary of Changes
<!-- อธิบายสรุปการเปลี่ยนแปลงและฟังก์ชันที่เพิ่มเข้ามา -->
- 

## Test Evidence & Quality Gates
<!-- บันทึกหลักฐานการทดสอบตามเกณฑ์ Definition of Done (DoD) สัปดาห์ 11-12 -->
- [ ] แบบทดสอบทั้งหมดผ่าน 100% (`python manage.py test`)
- [ ] Test Coverage รวม ≥ 80% (`coverage report -m --fail-under=80`)
- [ ] ผ่านการตรวจสอบ Formatter (`black --check --diff .`)
- [ ] ผ่านการตรวจสอบ Linter (`flake8 .` และ `ruff check .`)
- [ ] ผ่านการตรวจสอบความปลอดภัย (`bandit -r . -x '*/tests/*,*/migrations/*'`)
- [ ] ผ่านการตรวจสอบ Static Typing (`mypy --config-file mypy.ini`)

### Terminal Coverage Output
<!-- แปะภาพถ่ายหรือข้อความ Terminal ยืนยันผล coverage report -->
```text
(วางข้อความผลลัพธ์ของ coverage report ที่นี่)
```

## Checklist for Reviewer
- [ ] โค้ดตรงตามสถาปัตยกรรม (แยก write logic ใน `services.py` และ read logic ใน `selectors.py`)
- [ ] ทุกฟังก์ชัน View มีขนาดกะทัดรัด (Thin Views) และมี Docstrings ระบุรหัส `[UC-xx]`
- [ ] ทุกแบบฟอร์ม POST มีแท็ก `{% csrf_token %}` และมีการตรวจสอบสิทธิ์
- [ ] ไม่มี Hardcoded Secrets หรือ API Keys ในโค้ด
- [ ] ไม่พบปัญหา N+1 Query และมี Data Isolation แยกตามร้านอาหาร (`restaurant`) เสมอ
