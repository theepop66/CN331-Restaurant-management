from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import CustomUser, Restaurant


class RestaurantForm(forms.ModelForm):
    """[UC-01] Collects the tenant's basic info at sign-up time."""

    class Meta:
        model = Restaurant
        fields = ['name', 'address']
        labels = {
            'name': 'ชื่อร้าน',
            'address': 'ที่อยู่ร้าน',
        }
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'ชื่อร้าน',
                }
            ),
            'address': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'ที่อยู่ร้าน (ไม่บังคับ)',
                }
            ),
        }


class CustomUserCreationForm(UserCreationForm):
    """[UC-01] Registration form for the restaurant owner's account."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'name@example.com',
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ['username', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {
                'class': 'form-control',
                'placeholder': 'ชื่อผู้ใช้',
            }
        )
        self.fields['password1'].widget.attrs.update(
            {
                'class': 'form-control',
                'placeholder': 'รหัสผ่าน',
            }
        )
        self.fields['password2'].widget.attrs.update(
            {
                'class': 'form-control',
                'placeholder': 'ยืนยันรหัสผ่าน',
            }
        )

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('อีเมลนี้ถูกใช้งานแล้ว')
        return email


class LoginForm(AuthenticationForm):
    """[UC-01] Thin wrapper over AuthenticationForm for Bootstrap 5 classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {
                'class': 'form-control',
                'placeholder': 'ชื่อผู้ใช้',
                'autofocus': True,
            }
        )
        self.fields['password'].widget.attrs.update(
            {
                'class': 'form-control',
                'placeholder': 'รหัสผ่าน',
            }
        )
