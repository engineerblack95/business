from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import os

def supplier_document_path(instance, filename):
    """Generate file path for supplier documents"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('suppliers', str(instance.supplier.id), 'documents', filename)

def supplier_logo_path(instance, filename):
    """Generate file path for supplier logo"""
    ext = filename.split('.')[-1]
    filename = f"logo.{ext}"
    return os.path.join('suppliers', str(instance.id), filename)


# ============================================================
# SupplierProfile Model
# ============================================================

class SupplierProfile(models.Model):
    """Supplier profile with detailed information"""
    
    RATING_CHOICES = [
        (1, '⭐ Poor'),
        (2, '⭐⭐ Fair'),
        (3, '⭐⭐⭐ Good'),
        (4, '⭐⭐⭐⭐ Very Good'),
        (5, '⭐⭐⭐⭐⭐ Excellent'),
    ]
    
    VERIFICATION_STATUS = [
        ('unverified', 'Unverified'),
        ('pending', 'Verification Pending'),
        ('verified', 'Verified'),
        ('suspended', 'Suspended'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='supplier_profile'
    )
    
    # Business information
    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=50, blank=True, default='')
    logo = models.ImageField(upload_to=supplier_logo_path, blank=True, null=True)
    cover_image = models.ImageField(upload_to='suppliers/covers/', blank=True, null=True)
    
    # Contact
    business_phone = models.CharField(max_length=20)
    business_email = models.EmailField()
    business_address = models.TextField(blank=True, default='')
    business_city = models.CharField(max_length=100, blank=True, default='')
    business_country = models.CharField(max_length=100, default='Rwanda')
    website = models.URLField(blank=True)
    social_media = models.JSONField(default=dict, blank=True)
    
    # Business details
    description = models.TextField(blank=True, help_text="Business description and story")
    years_in_business = models.IntegerField(default=1)
    number_of_employees = models.IntegerField(default=1)
    
    # Performance metrics
    total_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_products_sold = models.IntegerField(default=0)
    total_products = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews = models.IntegerField(default=0)
    response_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    response_time = models.CharField(max_length=50, default='< 1 hour')
    
    # Verification
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='unverified')
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_documents = models.JSONField(default=list, blank=True)
    
    # Payment information
    payment_method = models.CharField(max_length=50, default='mobile_money')
    mobile_money_number = models.CharField(max_length=20, blank=True)
    bank_account_name = models.CharField(max_length=255, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_approve_products = models.BooleanField(default=False, help_text="Auto-approve products (trusted suppliers only)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['supplier']),
            models.Index(fields=['verification_status']),
            models.Index(fields=['average_rating']),
        ]
    
    def __str__(self):
        return f"{self.business_name} - {self.supplier.email}"
    
    def update_metrics(self):
        """Update supplier performance metrics"""
        from django.db.models import Sum, Avg, Count
        from products.models import Product
        from orders.models import OrderItem
        
        # Product stats
        products = Product.objects.filter(owner=self.supplier)
        self.total_products = products.count()
        self.total_products_sold = products.aggregate(total=Sum('sales_count'))['total'] or 0
        
        # Sales stats
        order_items = OrderItem.objects.filter(
            product__owner=self.supplier,
            order__payment_status__in=['simulated', 'paid']
        )
        self.total_sales = order_items.aggregate(total=Sum('final_price'))['total'] or 0
        
        # Rating stats
        from products.models import ProductReview
        reviews = ProductReview.objects.filter(product__owner=self.supplier)
        self.total_reviews = reviews.count()
        self.average_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        
        self.save()
    
    def get_rating_stars(self):
        """Return HTML for rating stars"""
        full_stars = int(self.average_rating)
        half_star = self.average_rating - full_stars >= 0.5
        empty_stars = 5 - full_stars - (1 if half_star else 0)
        
        stars = '⭐' * full_stars
        if half_star:
            stars += '½'
        stars += '☆' * empty_stars
        
        return stars


# ============================================================
# SupplierApplication Model
# ============================================================

class SupplierApplication(models.Model):
    """Supplier application model with document uploads"""
    
    APPLICATION_STATUS = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('additional_info', 'Additional Info Required'),
    ]
    
    BUSINESS_TYPES = [
        ('individual', 'Individual Seller'),
        ('sole_proprietorship', 'Sole Proprietorship'),
        ('partnership', 'Partnership'),
        ('limited_company', 'Limited Company'),
        ('corporation', 'Corporation'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(max_length=30, unique=True, editable=False)
    
    # Applicant information
    supplier = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='supplier_application'
    )
    
    # Business information
    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPES)
    tax_id = models.CharField(max_length=50, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    
    # Contact information
    business_phone = models.CharField(max_length=20)
    business_email = models.EmailField()
    business_address = models.TextField()
    business_city = models.CharField(max_length=100)
    business_country = models.CharField(max_length=100, default='Rwanda')
    
    # Documents
    business_license = models.FileField(
        upload_to=supplier_document_path,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'png', 'jpeg'])],
        help_text="Business registration certificate / license"
    )
    tax_clearance = models.FileField(
        upload_to=supplier_document_path,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'png', 'jpeg'])],
        blank=True,
        null=True,
        help_text="Tax clearance certificate"
    )
    id_document = models.FileField(
        upload_to=supplier_document_path,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'png', 'jpeg'])],
        help_text="National ID or Passport"
    )
    bank_statement = models.FileField(
        upload_to=supplier_document_path,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'png', 'jpeg'])],
        blank=True,
        null=True,
        help_text="Recent bank statement (for payout info)"
    )
    additional_documents = models.FileField(
        upload_to=supplier_document_path,
        blank=True,
        null=True,
        help_text="Any additional supporting documents"
    )
    
    # Product categories interested in
    interested_categories = models.ManyToManyField('products.Category', blank=True, related_name='interested_suppliers')
    
    # Additional information
    website = models.URLField(blank=True)
    years_in_business = models.IntegerField(default=1, validators=[MinValueValidator(0)])
    estimated_monthly_volume = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Estimated monthly sales volume in FRW"
    )
    notes = models.TextField(blank=True, help_text="Additional notes from supplier")
    
    # Application status
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='pending')
    rejection_reason = models.TextField(blank=True)
    additional_info_request = models.TextField(blank=True)
    
    # Review information
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application_number']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['business_name']),
            models.Index(fields=['supplier']),
        ]
    
    def __str__(self):
        return f"Application {self.application_number} - {self.business_name}"
    
    def save(self, *args, **kwargs):
        """Generate application number if not exists"""
        if not self.application_number:
            import secrets
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(4).upper()
            self.application_number = f"APP-{date_part}-{random_part}"
        super().save(*args, **kwargs)
    
    def approve(self, admin_user):
        """Approve supplier application - THIS CHANGES USER ROLE TO SUPPLIER"""
        self.status = 'approved'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.approved_at = timezone.now()
        self.save()
        
        # CRITICAL: Update user role from 'customer' to 'supplier'
        user = self.supplier
        user.role = 'supplier'
        user.is_approved_supplier = True
        user.business_name = self.business_name
        user.tax_id = self.tax_id
        user.save()
        
        # Create or update supplier profile - REMOVED tax_id (doesn't exist in SupplierProfile)
        profile, created = SupplierProfile.objects.get_or_create(
            supplier=user,
            defaults={
                'business_name': self.business_name,
                'business_type': self.business_type,
                'business_phone': self.business_phone,
                'business_email': self.business_email,
                'business_address': self.business_address,
                'business_city': self.business_city,
                'business_country': self.business_country,
                'website': self.website,
                'years_in_business': self.years_in_business,
                'verification_status': 'verified',
                'is_active': True
            }
        )
        
        if not created:
            # Update existing profile - REMOVED tax_id
            profile.business_name = self.business_name
            profile.business_type = self.business_type
            profile.business_phone = self.business_phone
            profile.business_email = self.business_email
            profile.business_address = self.business_address
            profile.business_city = self.business_city
            profile.business_country = self.business_country
            profile.website = self.website
            profile.years_in_business = self.years_in_business
            profile.verification_status = 'verified'
            profile.save()
        
        print(f"✅ User {user.email} role changed to: {user.role}")
    
    def reject(self, admin_user, reason):
        """Reject supplier application"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
    
    def request_additional_info(self, admin_user, message):
        """Request additional information from supplier"""
        self.status = 'additional_info'
        self.additional_info_request = message
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
    
    def get_status_badge_class(self):
        """Return CSS class for status badge"""
        status_classes = {
            'pending': 'warning',
            'reviewing': 'info',
            'approved': 'success',
            'rejected': 'danger',
            'additional_info': 'secondary',
        }
        return status_classes.get(self.status, 'secondary')


# ============================================================
# SupplierPayoutHistory Model
# ============================================================

class SupplierPayoutHistory(models.Model):
    """Track supplier payout history"""
    
    PAYOUT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYOUT_METHODS = [
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout_number = models.CharField(max_length=30, unique=True, editable=False)
    
    supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='supplier_payout_history'
    )
    
    # Payout details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_deducted = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    payment_method = models.CharField(max_length=20, choices=PAYOUT_METHODS)
    payment_details = models.JSONField(default=dict)
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS, default='pending')
    failure_reason = models.TextField(blank=True)
    
    # Order items included in this payout
    order_items = models.ManyToManyField('orders.OrderItem', related_name='supplier_payouts_list')
    
    # Processing information
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_processed_payouts'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Reference
    transaction_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Supplier Payout Histories"
        indexes = [
            models.Index(fields=['payout_number']),
            models.Index(fields=['supplier', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Payout {self.payout_number} - {self.supplier.email} - {self.amount} FRW"
    
    def save(self, *args, **kwargs):
        """Generate payout number if not exists"""
        if not self.payout_number:
            import secrets
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(4).upper()
            self.payout_number = f"PO-{date_part}-{random_part}"
        super().save(*args, **kwargs)
    
    def mark_as_completed(self, reference=''):
        """Mark payout as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if reference:
            self.transaction_reference = reference
        self.save()
    
    def mark_as_failed(self, reason):
        """Mark payout as failed"""
        self.status = 'failed'
        self.failure_reason = reason
        self.save()


# ============================================================
# SupplierPerformanceMetric Model
# ============================================================

class SupplierPerformanceMetric(models.Model):
    """Track supplier performance over time"""
    
    supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='supplier_performance_metrics'
    )
    
    # Date period
    period_date = models.DateField()
    period_type = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ])
    
    # Metrics
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    total_units_sold = models.IntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    new_products = models.IntegerField(default=0)
    products_approved = models.IntegerField(default=0)
    products_rejected = models.IntegerField(default=0)
    
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    response_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['supplier', 'period_date', 'period_type']
        ordering = ['-period_date']
    
    def __str__(self):
        return f"{self.supplier.email} - {self.period_date} - {self.period_type}"