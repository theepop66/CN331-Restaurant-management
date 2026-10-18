from django.urls import path

from . import views

app_name = 'menus'

urlpatterns = [
    path('', views.menu_list, name='list'),
    path('new/', views.menu_create, name='create'),
    path('<int:pk>/edit/', views.menu_update, name='update'),
    path('<int:pk>/recipe/', views.recipe_builder_view, name='recipe'),
    path('<int:pk>/availability/', views.menu_availability_update, name='availability'),
]
