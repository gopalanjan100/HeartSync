import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates a superuser from env vars if none exists"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            # Reset password in case it was created incorrectly before
            user = User.objects.filter(is_superuser=True).first()
            password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
            if password:
                user.set_password(password)
                user.save()
                self.stdout.write(f"Superuser '{user.username}' password reset.")
            else:
                self.stdout.write("Superuser already exists, skipping.")
            return

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set, skipping.")
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(f"Superuser '{username}' created successfully.")
