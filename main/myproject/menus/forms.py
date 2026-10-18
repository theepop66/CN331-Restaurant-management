from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from inventory.models import Ingredient

from .models import MenuItem, RecipeItem, normalize_name


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['name', 'price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0.01',
                    'step': '0.01',
                }
            ),
        }

    def clean_name(self):
        name = normalize_name(self.cleaned_data['name'])
        if (
            MenuItem.objects.filter(
                restaurant_id=self.instance.restaurant_id,
                normalized_name=name.casefold(),
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError('มีเมนูชื่อนี้ในร้านแล้ว')
        return name


class RevisionForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput())


class RecipeRevisionForm(RevisionForm):
    ingredient_state = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, menu, **kwargs):
        self.salt = f'menus.units.{menu.pk}'
        self.expected_units = {}
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update(
                expected_revision=menu.revision,
                ingredient_state=signing.dumps(
                    dict(
                        (str(pk), unit)
                        for pk, unit in Ingredient.objects.filter(
                            restaurant_id=menu.restaurant_id,
                        ).values_list('pk', 'unit')
                    ),
                    salt=self.salt,
                ),
            )

    def clean_ingredient_state(self):
        value = self.cleaned_data['ingredient_state']
        try:
            self.expected_units = signing.loads(value, salt=self.salt)
        except signing.BadSignature:
            raise ValidationError('ข้อมูลหน่วยนับไม่ถูกต้อง กรุณาโหลดหน้าใหม่') from None
        return value


class AvailabilityForm(RevisionForm):
    is_active = forms.BooleanField(required=False)


class IngredientChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.name} ({obj.get_unit_display()})'


class RecipeItemForm(forms.ModelForm):
    ingredient = IngredientChoiceField(
        queryset=Ingredient.objects.none(),
        label='วัตถุดิบ',
        empty_label='เลือกวัตถุดิบ',
        widget=forms.Select(attrs={'class': 'form-select ingredient-select'}),
    )

    class Meta:
        model = RecipeItem
        fields = ['ingredient', 'quantity_used']
        widgets = {
            'quantity_used': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0.001',
                    'step': '0.001',
                }
            )
        }

    def __init__(self, *args, restaurant, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ingredient'].queryset = Ingredient.objects.filter(restaurant=restaurant)

    def validate_constraints(self):
        # Validate the complete candidate in RecipeFormSet, then enforce the
        # database constraints after atomic replacement. Per-row uniqueness
        # against the OLD recipe would reject a valid ingredient swap.
        pass


class RecipeFormSet(BaseInlineFormSet):
    def get_unique_error_message(self, unique_check):
        return 'วัตถุดิบในสูตรต้องไม่ซ้ำกัน'

    def get_form_error(self):
        return 'วัตถุดิบในสูตรต้องไม่ซ้ำกัน'

    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields['id'].queryset = self.get_queryset()

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        expected_ids = set(self.get_queryset().values_list('pk', flat=True))
        submitted_ids = [
            form.cleaned_data['id'].pk for form in self.initial_forms if form.cleaned_data.get('id')
        ]
        if (
            len(submitted_ids) != len(expected_ids)
            or set(submitted_ids) != expected_ids
            or self.initial_form_count() != len(expected_ids)
        ):
            raise ValidationError('รายการสูตรอาหารไม่ตรงกับข้อมูลเดิม กรุณาโหลดหน้าใหม่')
        ingredients = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                ingredient = form.cleaned_data.get('ingredient')
                if ingredient:
                    ingredients.append(ingredient.pk)
        if not ingredients:
            raise ValidationError('ต้องมีวัตถุดิบอย่างน้อยหนึ่งรายการ')
        if len(set(ingredients)) != len(ingredients):
            raise ValidationError('วัตถุดิบในสูตรต้องไม่ซ้ำกัน')


RecipeItemFormSet = inlineformset_factory(
    MenuItem,
    RecipeItem,
    form=RecipeItemForm,
    formset=RecipeFormSet,
    fields=['ingredient', 'quantity_used'],
    extra=1,
    can_delete=True,
)
