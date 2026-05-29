from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class Notification(models.Model):
    """System notifications"""
    
    NOTIFICATION_TYPES = [
        ('order', 'Order Update'),
        ('payment', 'Payment Update'),
        ('product', 'Product Update'),
        ('supplier', 'Supplier Update'),
        ('commission', 'Commission Update'),
        ('payout', 'Payout Update'),
        ('system', 'System Notification'),
        ('alert', 'Alert'),
        ('promotion', 'Promotion'),
        ('reminder', 'Reminder'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Action link
    link = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=50, blank=True, default='View Details')
    
    # Icons
    icon = models.CharField(max_length=50, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Email tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    # SMS tracking (for future)
    sms_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def get_icon_class(self):
        """Get Font Awesome icon class"""
        icons = {
            'order': 'fa-shopping-cart',
            'payment': 'fa-credit-card',
            'product': 'fa-box',
            'supplier': 'fa-store',
            'commission': 'fa-coins',
            'payout': 'fa-money-bill-wave',
            'system': 'fa-cog',
            'alert': 'fa-exclamation-triangle',
            'promotion': 'fa-tag',
            'reminder': 'fa-bell',
        }
        return icons.get(self.notification_type, 'fa-bell')


class NotificationPreference(models.Model):
    """User notification preferences"""
    
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('push', 'Push Notification'),
        ('sms', 'SMS'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_prefs')
    
    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    
    # Type preferences
    order_notifications = models.BooleanField(default=True)
    payment_notifications = models.BooleanField(default=True)
    product_notifications = models.BooleanField(default=True)
    supplier_notifications = models.BooleanField(default=True)
    commission_notifications = models.BooleanField(default=True)
    promotional_notifications = models.BooleanField(default=False)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.email}"
    
    def should_send(self, notification_type):
        """Check if user wants this type of notification"""
        mapping = {
            'order': self.order_notifications,
            'payment': self.payment_notifications,
            'product': self.product_notifications,
            'supplier': self.supplier_notifications,
            'commission': self.commission_notifications,
            'promotion': self.promotional_notifications,
        }
        return mapping.get(notification_type, True)


class NotificationTemplate(models.Model):
    """Email/SMS notification templates"""
    
    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=200)
    template = models.TextField()
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name