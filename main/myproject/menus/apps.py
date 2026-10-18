from django.apps import AppConfig


class MenusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'menus'

    def ready(self):
        from . import signals  # noqa: F401
