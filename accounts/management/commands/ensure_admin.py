from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Ensures that an admin user exists based on environment variables'

    def handle(self, *args, **options):
        email = os.environ.get('ADMIN_USERNAME')
        password = os.environ.get('ADMIN_PASSWORD')

        if not email or not password:
            self.stdout.write(self.style.WARNING('ADMIN_USERNAME and ADMIN_PASSWORD not set, skipping admin creation'))
            return

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'full_name': 'Admin',
                'role': 'admin',
                'is_superuser': True,
                'is_staff': True,
                'is_verified': True,
            }
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created superuser {email}'))
        else:
            # Update existing user
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.role = 'admin'
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Updated superuser {email}'))