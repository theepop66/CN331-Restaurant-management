"""[US-04] URLs for orders app."""

from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.pos_view, name='pos'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('<int:pk>/success/', views.order_success_view, name='success'),
]
