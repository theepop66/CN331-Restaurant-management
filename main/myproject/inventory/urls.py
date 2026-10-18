from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.ingredient_list, name='list'),
    path('new/', views.ingredient_create, name='create'),
    path('scan/', views.scan, name='scan'),
    path('<int:pk>/', views.ingredient_detail, name='detail'),
    path('<int:pk>/edit/', views.ingredient_update, name='update'),
    path('<int:pk>/delete/', views.ingredient_delete, name='delete'),
    path('<int:pk>/stock-in/', views.stock_in, name='stock_in'),
]
