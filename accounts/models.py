from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
import uuid
import secrets

class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, phone, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        if not phone:
            raise ValueError('Phone number is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User Model with role-based access"""
    
    ROLE_CHOICES = [
        ('admin', 'Admin/Owner'),
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('team_member', 'Team Member'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(validators=[phone_regex], max_length=17, unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    
    # OTP fields
    otp_secret = models.CharField(max_length=32, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    otp_attempts = models.IntegerField(default=0)
    
    # Account status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    # Supplier specific fields
    business_name = models.CharField(max_length=255, blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    is_approved_supplier = models.BooleanField(default=False)
    
    # Team member specific fields
    team_permissions = models.JSONField(default=dict, blank=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone']
    
    class Meta:
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['is_approved_supplier']),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    def generate_otp(self):
        """Generate a 6-digit OTP"""
        import random
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.otp_secret = otp
        self.otp_created_at = timezone.now()
        self.otp_attempts = 0
        self.save(update_fields=['otp_secret', 'otp_created_at', 'otp_attempts'])
        return otp
    
    def verify_otp(self, otp):
        """Verify OTP with expiry check"""
        from django.conf import settings
        
        if not self.otp_secret or not self.otp_created_at:
            return False
        
        # Check expiry
        expiry_minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
        if (timezone.now() - self.otp_created_at).seconds > (expiry_minutes * 60):
            return False
        
        # Check attempts
        if self.otp_attempts >= 5:
            return False
        
        # Verify OTP
        if self.otp_secret == otp:
            self.otp_secret = None
            self.otp_created_at = None
            self.otp_attempts = 0
            self.is_verified = True
            self.save(update_fields=['otp_secret', 'otp_created_at', 'otp_attempts', 'is_verified'])
            return True
        
        self.otp_attempts += 1
        self.save(update_fields=['otp_attempts'])
        return False
    
    def has_permission(self, permission):
        """Check if team member has specific permission"""
        if self.role == 'admin':
            return True
        if self.role == 'team_member':
            return self.team_permissions.get(permission, False)
        return False
    
    def get_dashboard_url(self):
        """Return the appropriate dashboard URL based on role"""
        if self.role == 'admin':
            return '/dashboard/admin/'
        elif self.role == 'supplier':
            return '/dashboard/supplier/'
        elif self.role == 'team_member':
            return '/dashboard/team/'
        else:
            return '/dashboard/customer/'


class UserLoginHistory(models.Model):
    """Track all user logins with device and location information"""
    
    DEVICE_TYPES = [
        ('pc', 'PC/Laptop'),
        ('smartphone', 'Smartphone'),
        ('tablet', 'Tablet'),
        ('bot', 'Bot/Crawler'),
        ('unknown', 'Unknown'),
    ]
    
    OS_TYPES = [
        ('windows', 'Windows'),
        ('macos', 'macOS'),
        ('linux', 'Linux'),
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('chromeos', 'Chrome OS'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    
    # Timestamps
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(blank=True, null=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    
    # Network information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Location data
    location_country = models.CharField(max_length=100, blank=True)
    location_city = models.CharField(max_length=100, blank=True)
    location_region = models.CharField(max_length=100, blank=True)
    location_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    location_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    # Device information - Enhanced
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='unknown')
    device_display = models.CharField(max_length=50, blank=True, default='')  # Human readable device name
    device_brand = models.CharField(max_length=100, blank=True, default='')   # e.g., Apple, Samsung
    device_model = models.CharField(max_length=100, blank=True, default='')   # e.g., iPhone 13, Galaxy S21
    
    # OS information - Enhanced
    os_type = models.CharField(max_length=20, choices=OS_TYPES, default='unknown')
    os_display = models.CharField(max_length=100, blank=True, default='')     # Human readable OS name with version
    
    # Browser information - Enhanced
    browser = models.CharField(max_length=100, blank=True)
    browser_version = models.CharField(max_length=50, blank=True)
    browser_display = models.CharField(max_length=100, blank=True, default='') # Human readable browser name
    
    class Meta:
        ordering = ['-login_time']
        verbose_name_plural = "User Login Histories"
        indexes = [
            models.Index(fields=['user', '-login_time']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['login_time']),
            models.Index(fields=['device_type']),
            models.Index(fields=['os_type']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.login_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def get_location_display(self):
        """Return formatted location string"""
        if self.location_city and self.location_country:
            return f"{self.location_city}, {self.location_country}"
        elif self.location_country:
            return self.location_country
        elif self.location_region:
            return self.location_region
        return "Unknown location"
    
    def get_duration(self):
        """Calculate session duration in minutes"""
        if self.logout_time:
            duration = (self.logout_time - self.login_time).total_seconds() / 60
            return round(duration, 2)
        return None
    
    def get_device_full_name(self):
        """Return full device name with brand and model"""
        if self.device_brand and self.device_model:
            return f"{self.device_brand} {self.device_model}"
        elif self.device_display:
            return self.device_display
        return self.get_device_type_display()
    
    def get_os_full_name(self):
        """Return full OS name with version"""
        if self.os_display:
            return self.os_display
        return self.get_os_type_display()
    
    def get_browser_full_name(self):
        """Return full browser name with version"""
        if self.browser_display:
            if self.browser_version:
                return f"{self.browser_display} {self.browser_version}"
            return self.browser_display
        if self.browser:
            if self.browser_version:
                return f"{self.browser} {self.browser_version}"
            return self.browser
        return "Unknown browser"
    
    def get_device_icon(self):
        """Return Font Awesome icon class for device type"""
        icons = {
            'pc': 'fa-desktop',
            'smartphone': 'fa-mobile-alt',
            'tablet': 'fa-tablet-alt',
            'bot': 'fa-robot',
            'unknown': 'fa-question-circle'
        }
        return icons.get(self.device_type, 'fa-laptop')
    
    def get_os_icon(self):
        """Return Font Awesome icon class for OS type"""
        icons = {
            'windows': 'fa-windows',
            'macos': 'fa-apple',
            'linux': 'fa-linux',
            'android': 'fa-android',
            'ios': 'fa-mobile',
            'chromeos': 'fa-chrome',
            'unknown': 'fa-question-circle'
        }
        return icons.get(self.os_type, 'fa-microchip')
    
    def get_browser_icon(self):
        """Return Font Awesome icon class for browser"""
        browser_lower = self.browser.lower()
        if 'chrome' in browser_lower:
            return 'fa-chrome'
        elif 'firefox' in browser_lower:
            return 'fa-firefox'
        elif 'safari' in browser_lower:
            return 'fa-safari'
        elif 'edge' in browser_lower:
            return 'fa-edge'
        elif 'opera' in browser_lower:
            return 'fa-opera'
        else:
            return 'fa-globe'