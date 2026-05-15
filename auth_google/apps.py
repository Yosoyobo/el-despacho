from django.apps import AppConfig


class AuthGoogleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "auth_google"
    verbose_name = "Auth — Google SSO"
