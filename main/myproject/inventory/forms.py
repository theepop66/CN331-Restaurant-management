from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import Ingredient

ZERO = Decimal('0')
MIN_STOCK_IN = Decimal('0.001')


def _today():
    return timezone.localdate()


class IngredientForm(forms.ModelForm):
    """
    [UC-02] สร้าง/แก้ไขวัตถุดิบ.

    - ต้องส่ง restaurant เข้ามา (ฟอร์มไม่ให้ผู้ใช้เลือกร้านเอง)
    - ตอนสร้าง: มี "วันหมดอายุ" (ไม่บังคับ) ซึ่งผูกกับปริมาณเริ่มต้น
      ถ้าปริมาณ > 0 view จะสร้างล็อตแรกให้
    - ตอนแก้ไข: แก้ยอดสต็อกตรง ๆ ได้ (เป็นการปรับยอด ไม่บันทึกเป็น StockIn)
    """

    expiry_date = forms.DateField(
        label='วันหมดอายุ (ของปริมาณเริ่มต้น)',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    class Meta:
        model = Ingredient
        fields = ['name', 'barcode', 'unit', 'price', 'stock_quantity']
        labels = {
            'name': 'ชื่อวัตถุดิบ',
            'barcode': 'บาร์โค้ด',
            'unit': 'หน่วย',
            'price': 'ราคาต่อหน่วย (บาท)',
            'stock_quantity': 'ปริมาณ',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'เช่น ข้าวสาร',
                'list': 'ingredient-names',
                'autocomplete': 'off',
            }),
            'barcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'สแกนหรือพิมพ์บาร์โค้ด (ไม่บังคับ)',
            }),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.01',
            }),
            'stock_quantity': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.001',
            }),
        }

    def __init__(self, *args, restaurant, **kwargs):
        super().__init__(*args, **kwargs)
        self.restaurant = restaurant
        self.fields['unit'].choices = [('', 'เลือกหน่วย')] + list(
            Ingredient.Unit.choices
        )
        self.fields['price'].required = True
        if self.instance.pk:
            # แก้ไขวัตถุดิบเดิม: ไม่มีช่องวันหมดอายุ (วันหมดอายุอยู่ที่ล็อต)
            del self.fields['expiry_date']
            self.fields['stock_quantity'].label = 'ปริมาณคงเหลือ (ปรับยอด)'
        else:
            self.fields['stock_quantity'].label = 'ปริมาณเริ่มต้น'
            self.fields['stock_quantity'].required = False

    def _others(self):
        qs = Ingredient.objects.filter(restaurant=self.restaurant)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        return qs

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if not name:
            raise forms.ValidationError('กรุณากรอกชื่อวัตถุดิบ')
        if self._others().filter(name__iexact=name).exists():
            raise forms.ValidationError('มีวัตถุดิบชื่อนี้ในร้านแล้ว')
        return name

    def clean_barcode(self):
        barcode = (self.cleaned_data.get('barcode') or '').strip()
        if not barcode:
            return ''
        if barcode.upper().startswith(Ingredient.GENERATED_BARCODE_PREFIX):
            raise forms.ValidationError(
                f'รหัสที่ขึ้นต้นด้วย "{Ingredient.GENERATED_BARCODE_PREFIX}" '
                'สงวนไว้ให้ระบบสร้างอัตโนมัติ'
            )
        if self._others().filter(barcode=barcode).exists():
            raise forms.ValidationError('บาร์โค้ดนี้ถูกใช้กับวัตถุดิบอื่นในร้านแล้ว')
        return barcode

    def clean_price(self):
        price = self.cleaned_data['price']
        if price < ZERO:
            raise forms.ValidationError('ราคาต้องไม่ติดลบ')
        return price

    def clean_stock_quantity(self):
        qty = self.cleaned_data.get('stock_quantity')
        if qty is None:
            return ZERO
        if qty < ZERO:
            raise forms.ValidationError('ปริมาณต้องไม่ติดลบ')
        return qty

    def clean(self):
        cleaned = super().clean()
        expiry = cleaned.get('expiry_date')
        qty = cleaned.get('stock_quantity')
        if expiry:
            if expiry < _today():
                self.add_error('expiry_date', 'ไม่สามารถรับของที่หมดอายุแล้วเข้าคลังได้')
            elif qty is not None and qty <= ZERO:
                self.add_error(
                    'expiry_date',
                    'วันหมดอายุใช้กับปริมาณเริ่มต้นเท่านั้น กรุณากรอกปริมาณมากกว่า 0',
                )
        return cleaned


class StockInForm(forms.Form):
    """[UC-02] รับเข้าสต็อก: จำนวน (> 0) + วันหมดอายุของล็อต (ไม่บังคับ)."""

    quantity = forms.DecimalField(
        label='จำนวนที่รับเข้า',
        max_digits=12, decimal_places=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'min': '0.001', 'step': '0.001',
        }),
        error_messages={
            'required': 'กรุณากรอกจำนวนที่รับเข้า',
            'invalid': 'จำนวนต้องเป็นตัวเลข',
        },
    )
    expiry_date = forms.DateField(
        label='วันหมดอายุของล็อตนี้',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    def clean_quantity(self):
        qty = self.cleaned_data['quantity']
        if qty < MIN_STOCK_IN:
            raise forms.ValidationError('จำนวนที่รับเข้าต้องมากกว่า 0')
        return qty

    def clean_expiry_date(self):
        expiry = self.cleaned_data.get('expiry_date')
        if expiry and expiry < _today():
            raise forms.ValidationError('ไม่สามารถรับของที่หมดอายุแล้วเข้าคลังได้')
        return expiry


class ScanForm(forms.Form):
    """[UC-02] ช่องสแกน/พิมพ์บาร์โค้ด + โหมดสแกนรัว (บวกครั้งละ 1 ตายตัว)."""

    barcode = forms.CharField(
        label='บาร์โค้ด',
        max_length=64,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'สแกนหรือพิมพ์บาร์โค้ดแล้วกด Enter',
            'autofocus': True,
            'autocomplete': 'off',
        }),
    )
    quick_mode = forms.BooleanField(
        label='สแกนรัว',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean_barcode(self):
        return self.cleaned_data['barcode'].strip()
