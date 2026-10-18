"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # UC-01 (คนที่ 1): auth + tenant routes, mounted at the site root.
    path('', include('accounts.urls')),

    path('inventory/', include('inventory.urls')),    # UC-02 (คนที่ 2)
    # path('menus/', include('menus.urls')),          # UC-03 (คนที่ 3)
    # path('orders/', include('orders.urls')),        # UC-04 (คนที่ 4)
    # path('analytics/', include('analytics.urls')),  # UC-05, UC-06 (คนที่ 5)
]
