from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import os
from cloudinary.models import CloudinaryField  # Add this import


class Category(models.Model):
    """Product categories"""
    
    CATEGORY_TYPES = [
        ('laptops', 'Laptops'),
        ('phones', 'Smartphones'),
        ('tvs', 'Televisions'),
        ('audio', 'Audio Equipment'),
        ('tablets', 'Tablets'),
        ('components', 'Computer Components'),
        ('accessories', 'Accessories'),
        ('gaming', 'Gaming'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='other')
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_icon_class(self):
        """Return Font Awesome icon class"""
        icons = {
            'laptops': 'fa-laptop',
            'phones': 'fa-mobile-alt',
            'tvs': 'fa-tv',
            'audio': 'fa-headphones',
            'tablets': 'fa-tablet-alt',
            'components': 'fa-microchip',
            'accessories': 'fa-keyboard',
            'gaming': 'fa-gamepad',
            'other': 'fa-box',
        }
        return icons.get(self.category_type, 'fa-box')


class Product(models.Model):
    """Product model with approval workflow and stock management"""
    
    PRODUCT_STATUS = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('out_of_stock', 'Out of Stock'),
        ('discontinued', 'Discontinued'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, max_length=255)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    
    # Categorization
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    subcategory = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_products')
    
    # Pricing (VAT included logic)
    base_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price excluding VAT"
    )
    vat_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        editable=False, 
        default=0
    )
    final_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        editable=False,
        help_text="Price including VAT (shown to customers)"
    )
    
    # Stock Management (EXACT quantity - only visible to admin/supplier)
    exact_quantity = models.IntegerField(
        default=0, 
        validators=[MinValueValidator(0)],
        help_text="Exact stock quantity - only visible to Admin and Supplier"
    )
    low_stock_threshold = models.IntegerField(default=5, help_text="Alert when stock falls below this number")
    
    # Product Ownership (CRITICAL: determines commission logic)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='products'
    )
    is_supplier_product = models.BooleanField(default=False, help_text="True if posted by supplier, False if by admin")
    
    # Approval Workflow
    status = models.CharField(max_length=20, choices=PRODUCT_STATUS, default='draft')
    approval_status = models.CharField(max_length=20, choices=PRODUCT_STATUS, default='pending_approval')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_products'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection if applicable")
    
    # Product Specifications
    brand = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    warranty_months = models.IntegerField(default=12, validators=[MinValueValidator(0)])
    
    # Media - UPDATED to use CloudinaryField
    main_image = CloudinaryField(
        'image',
        folder='heros_technology/products/',
        blank=True,
        null=True,
        transformation={'quality': 'auto', 'fetch_format': 'auto'}
    )
    images = models.ManyToManyField('ProductImage', blank=True, related_name='product_images')
    
    # SEO & Metadata
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True, max_length=500)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags for search")
    
    # Metrics
    views_count = models.IntegerField(default=0)
    sales_count = models.IntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'approval_status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['owner', 'is_supplier_product']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['brand']),
            models.Index(fields=['sales_count']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.owner.email}"
    
    def save(self, *args, **kwargs):
        """Override save to calculate VAT and generate slug"""
        
        # Calculate VAT (18%)
        from django.conf import settings
        vat_rate = Decimal(str(getattr(settings, 'VAT_RATE', 18))) / Decimal('100')
        self.vat_amount = (self.base_price * vat_rate).quantize(Decimal('0.01'))
        self.final_price = (self.base_price + self.vat_amount).quantize(Decimal('0.01'))
        
        # Generate slug if not exists
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(f"{self.name}-{uuid.uuid4().hex[:8]}")
        
        # FIXED: Only auto-update status based on stock if status is 'approved' or 'out_of_stock'
        if self.status == 'approved' and self.exact_quantity == 0:
            if not hasattr(self, '_skip_auto_status'):
                self.status = 'out_of_stock'
        elif self.status == 'out_of_stock' and self.exact_quantity > 0:
            self.status = 'approved'
        
        super().save(*args, **kwargs)
    
    def get_stock_label(self, user=None):
        """
        Return stock label based on user role
        - Customer: "In Stock" or "Out of Stock"
        - Supplier (owner): Exact quantity
        - Admin: Exact quantity
        """
        if user and user.is_authenticated:
            if user.role == 'admin':
                return f"{self.exact_quantity} units"
            elif user.role == 'supplier' and self.owner == user:
                return f"{self.exact_quantity} units remaining"
        
        if self.exact_quantity > 0:
            return "In Stock"
        else:
            return "Out of Stock"
    
    def get_stock_badge_class(self):
        """Return Bootstrap badge class based on stock status"""
        if self.exact_quantity > 10:
            return "success"
        elif self.exact_quantity > 0:
            return "warning"
        else:
            return "danger"
    
    def is_in_stock(self):
        """Check if product is in stock (for customers)"""
        return self.exact_quantity > 0 and self.status == 'approved'
    
    def decrease_stock(self, quantity):
        """Decrease stock when product is purchased"""
        if self.exact_quantity >= quantity:
            self.exact_quantity -= quantity
            self.sales_count += quantity
            self.save()
            return True
        return False
    
    def increase_stock(self, quantity):
        """Increase stock (returns, restocking)"""
        self.exact_quantity += quantity
        self.save()
    
    def is_low_stock(self):
        """Check if stock is below threshold"""
        return self.exact_quantity <= self.low_stock_threshold and self.exact_quantity > 0
    
    def calculate_performance_score(self):
        """Calculate product performance score for ranking"""
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        
        try:
            from orders.models import OrderItem
            recent_sales = OrderItem.objects.filter(
                product=self,
                order__created_at__gte=thirty_days_ago,
                order__payment_status='paid'
            ).count()
        except (ImportError, Exception):
            recent_sales = 0
        
        recent_views = self.views_count
        
        score = (recent_sales * 2) + (float(self.rating) * 10) + (recent_views * 0.5)
        return round(score, 2)
    
    def get_owner_name_for_display(self):
        """
        CRITICAL: Returns owner name for display
        - Always returns "HerosTechnology" to hide supplier identity
        """
        return "HerosTechnology"
    
    def get_commission_amount(self):
        """Calculate commission for supplier products (7% of base_price)"""
        if self.is_supplier_product:
            from django.conf import settings
            commission_rate = Decimal(str(getattr(settings, 'COMMISSION_RATE', 7))) / Decimal('100')
            return (self.base_price * commission_rate).quantize(Decimal('0.01'))
        return Decimal('0.00')
    
    def get_supplier_payout(self):
        """Calculate supplier payout amount after commission"""
        if self.is_supplier_product:
            return (self.base_price - self.get_commission_amount()).quantize(Decimal('0.01'))
        return Decimal('0.00')


class ProductImage(models.Model):
    """Additional product images - UPDATED to use CloudinaryField"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='additional_images')
    image = CloudinaryField(
        'image',
        folder='heros_technology/products/gallery/',
        blank=True,
        null=True,
        transformation={'quality': 'auto', 'fetch_format': 'auto'}
    )
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Image for {self.product.name}"


class ProductReview(models.Model):
    """Customer reviews and ratings for products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=200)
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    helpful_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'customer']
    
    def __str__(self):
        return f"{self.customer.email} - {self.product.name} - {self.rating} stars"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.db.models import Avg
        avg_rating = ProductReview.objects.filter(
            product=self.product, 
            is_approved=True
        ).aggregate(Avg('rating'))['rating__avg']
        
        if avg_rating:
            self.product.rating = round(avg_rating, 2)
            self.product.rating_count = ProductReview.objects.filter(
                product=self.product, 
                is_approved=True
            ).count()
            self.product.save()


class Wishlist(models.Model):
    """Customer wishlist"""
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['customer', 'product']
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.customer.email} - {self.product.name}"


class ProductViewHistory(models.Model):
    """Track product views for analytics"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='view_history')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, db_index=True)
    ip_address = models.GenericIPAddressField()
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['product', '-viewed_at']),
            models.Index(fields=['session_key']),
        ]
    
    def __str__(self):
        return f"{self.product.name} viewed at {self.viewed_at}"


class StockMovement(models.Model):
    """Track all stock movements"""
    MOVEMENT_TYPES = [
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('restock', 'Restock'),
        ('release', 'Release'),
        ('adjustment', 'Adjustment'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField()
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['movement_type']),
        ]
    
    def __str__(self):
        return f"{self.movement_type}: {self.quantity} of {self.product.name}"