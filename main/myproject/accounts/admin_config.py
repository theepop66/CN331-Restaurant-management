from django.contrib.admin.apps import AdminConfig


class OwnerAdminConfig(AdminConfig):
    default_site = 'accounts.admin_site.OwnerAdminSite'
