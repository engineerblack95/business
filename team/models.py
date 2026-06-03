from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from cloudinary.models import CloudinaryField  # Add this import


class TeamMember(models.Model):
    """Team members for About page display"""
    
    POSITION_CHOICES = [
        ('ceo', 'CEO / Founder'),
        ('cto', 'CTO / Technical Director'),
        ('operations', 'Operations Manager'),
        ('sales', 'Sales Manager'),
        ('support', 'Customer Support'),
        ('marketing', 'Marketing Specialist'),
        ('procurement', 'Procurement Specialist'),
        ('logistics', 'Logistics Coordinator'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_display'
    )
    
    # Personal information
    full_name = models.CharField(max_length=255)
    position = models.CharField(max_length=50, choices=POSITION_CHOICES)
    custom_position = models.CharField(max_length=100, blank=True, help_text="If position is 'Other'")
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    
    # Media - UPDATED to use CloudinaryField
    profile_image = CloudinaryField(
        'image',
        folder='heros_technology/team/',
        blank=True,
        null=True,
        transformation={'width': 300, 'height': 300, 'crop': 'fill', 'gravity': 'face', 'quality': 'auto'}
    )
    
    # Bio
    bio = models.TextField(help_text="Short biography of team member")
    expertise = models.TextField(blank=True, help_text="Areas of expertise, comma separated")
    achievements = models.TextField(blank=True, help_text="Key achievements")
    
    # Social media links
    linkedin = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    
    # Display settings
    display_order = models.IntegerField(default=0, help_text="Lower number appears first")
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False, help_text="Show on homepage")
    
    # Statistics (auto-updated)
    tasks_completed = models.IntegerField(default=0)
    customer_satisfaction = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Timestamps
    joined_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', '-joined_at']
        indexes = [
            models.Index(fields=['is_active', 'display_order']),
            models.Index(fields=['featured']),
        ]
    
    def __str__(self):
        return f"{self.full_name} - {self.get_position_display()}"
    
    def get_display_position(self):
        """Get position display name"""
        if self.position == 'other' and self.custom_position:
            return self.custom_position
        return self.get_position_display()
    
    def get_expertise_list(self):
        """Return expertise as list"""
        return [e.strip() for e in self.expertise.split(',') if e.strip()]


class TeamTask(models.Model):
    """Tasks assigned to team members"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('review', 'Under Review'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_tasks'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks'
    )
    
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    due_date = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Related to specific system objects
    related_order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    related_product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    related_supplier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_tasks')
    
    # Task notes
    notes = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'due_date']
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.assigned_to.email}"
    
    def mark_completed(self):
        """Mark task as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        
        # Update team member task count
        if hasattr(self.assigned_to, 'team_display'):
            team_member = self.assigned_to.team_display
            team_member.tasks_completed += 1
            team_member.save()
    
    def is_overdue(self):
        """Check if task is overdue"""
        return self.status != 'completed' and timezone.now() > self.due_date


class TeamActivity(models.Model):
    """Track team member activities"""
    
    ACTIVITY_TYPES = [
        ('task_created', 'Task Created'),
        ('task_completed', 'Task Completed'),
        ('order_processed', 'Order Processed'),
        ('supplier_approved', 'Supplier Approved'),
        ('product_approved', 'Product Approved'),
        ('customer_responded', 'Customer Responded'),
        ('report_generated', 'Report Generated'),
    ]
    
    team_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    related_object_id = models.CharField(max_length=100, blank=True)
    related_object_type = models.CharField(max_length=100, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Team Activities"
    
    def __str__(self):
        return f"{self.team_member.email} - {self.activity_type} - {self.created_at}"