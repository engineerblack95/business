from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import secrets


class Cart(models.Model):
    """Shopping cart for customers"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['customer']),
        ]
    
    def __str__(self):
        return f"Cart for {self.customer.email}"
    
    def get_total_base_price(self):
        """Calculate total base price (excl VAT)"""
        from decimal import Decimal
        items = self.items.all()
        if not items:
            return Decimal('0.00')
        total = sum(item.get_base_price() for item in items)
        if isinstance(total, int):
            total = Decimal(total)
        return total.quantize(Decimal('0.01'))
    
    def get_total_vat(self):
        """Calculate total VAT amount"""
        from decimal import Decimal
        items = self.items.all()
        if not items:
            return Decimal('0.00')
        total = sum(item.get_vat_amount() for item in items)
        if isinstance(total, int):
            total = Decimal(total)
        return total.quantize(Decimal('0.01'))
    
    def get_grand_total(self):
        """Calculate grand total (including VAT)"""
        from decimal import Decimal
        items = self.items.all()
        if not items:
            return Decimal('0.00')
        total = sum(item.get_final_price() for item in items)
        if isinstance(total, int):
            total = Decimal(total)
        return total.quantize(Decimal('0.01'))
    
    def get_total_items(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items.all())
    
    def clear_cart(self):
        """Clear all items from cart"""
        self.items.all().delete()
    
    def is_empty(self):
        """Check if cart is empty"""
        return self.items.count() == 0


class CartItem(models.Model):
    """Individual items in shopping cart"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    
    snapshot_base_price = models.DecimalField(max_digits=12, decimal_places=2)
    snapshot_vat_amount = models.DecimalField(max_digits=12, decimal_places=2)
    snapshot_final_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['cart', 'product']
        ordering = ['-added_at']
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
    
    def save(self, *args, **kwargs):
        """Take snapshot of product prices when adding to cart"""
        from decimal import Decimal
        if not self.snapshot_base_price:
            self.snapshot_base_price = Decimal(str(self.product.base_price))
            self.snapshot_vat_amount = Decimal(str(self.product.vat_amount))
            self.snapshot_final_price = Decimal(str(self.product.final_price))
        super().save(*args, **kwargs)
    
    def get_base_price(self):
        """Get total base price for this item"""
        from decimal import Decimal
        return (Decimal(str(self.snapshot_base_price)) * self.quantity).quantize(Decimal('0.01'))
    
    def get_vat_amount(self):
        """Get total VAT for this item"""
        from decimal import Decimal
        return (Decimal(str(self.snapshot_vat_amount)) * self.quantity).quantize(Decimal('0.01'))
    
    def get_final_price(self):
        """Get total final price for this item"""
        from decimal import Decimal
        return (Decimal(str(self.snapshot_final_price)) * self.quantity).quantize(Decimal('0.01'))


class Order(models.Model):
    """Order model with complete tracking"""
    
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash_on_delivery', 'Cash on Delivery'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('simulated', 'Simulated Payment'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    
    subtotal_base = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total base price excl VAT")
    total_vat = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total VAT amount")
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total including VAT")
    
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100, blank=True, default='')
    shipping_phone = models.CharField(max_length=20)
    shipping_notes = models.TextField(blank=True)
    
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='mobile_money')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    
    tracking_number = models.CharField(max_length=100, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['order_status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer.email}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(3).upper()
            self.order_number = f"ORD-{date_part}-{random_part}"
        super().save(*args, **kwargs)
    
    def get_commission_total(self):
        total_commission = Decimal('0.00')
        for item in self.items.all():
            total_commission += item.commission_amount
        return total_commission.quantize(Decimal('0.01'))
    
    def get_supplier_payouts(self):
        from django.db.models import Sum
        return self.items.filter(product__is_supplier_product=True).values(
            'product__owner'
        ).annotate(
            total_amount=Sum('supplier_payout_amount')
        )
    
    def can_be_cancelled(self):
        return self.order_status in ['pending', 'paid'] and self.payment_status != 'refunded'
    
    def cancel_order(self):
        if self.can_be_cancelled():
            for item in self.items.all():
                item.product.increase_stock(item.quantity)
                item.status = 'cancelled'
                item.save()
            self.order_status = 'cancelled'
            self.save()
            return True
        return False


class OrderItem(models.Model):
    """Individual items in an order"""
    
    ITEM_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='order_items')
    
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2)
    final_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    is_supplier_product = models.BooleanField(default=False)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier_payout_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=ITEM_STATUS_CHOICES, default='pending')
    
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order', 'product']),
            models.Index(fields=['is_supplier_product']),
        ]
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Order {self.order.order_number})"
    
    def save(self, *args, **kwargs):
        from django.conf import settings
        
        if self.is_supplier_product:
            commission_rate = Decimal(str(getattr(settings, 'COMMISSION_RATE', 7))) / Decimal('100')
            self.commission_amount = (self.base_price * commission_rate * self.quantity).quantize(Decimal('0.01'))
            self.supplier_payout_amount = ((self.base_price - (self.base_price * commission_rate)) * self.quantity).quantize(Decimal('0.01'))
        
        super().save(*args, **kwargs)
    
    def get_total_base_price(self):
        return (self.base_price * self.quantity).quantize(Decimal('0.01'))
    
    def get_total_vat(self):
        return (self.vat_amount * self.quantity).quantize(Decimal('0.01'))
    
    def get_total_final_price(self):
        return (self.final_price * self.quantity).quantize(Decimal('0.01'))
    
    def get_commission_amount(self):
        return self.commission_amount


class PaymentTransaction(models.Model):
    """Track all payment transactions"""
    
    TRANSACTION_STATUS = [
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transactions')
    
    transaction_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='payment_transactions',
        null=True,
        blank=True
    )
    
    mobile_money_number = models.CharField(max_length=20, blank=True)
    provider = models.CharField(max_length=50, default='simulated')
    
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='initiated')
    status_message = models.TextField(blank=True)
    provider_reference = models.CharField(max_length=100, blank=True)
    provider_transaction_id = models.CharField(max_length=100, blank=True)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    webhook_data = models.JSONField(default=dict, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    initiated_at = models.DateTimeField(auto_now_add=True)
    processing_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['customer', '-created_at']),
        ]
    
    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.status}"


class CommissionEarning(models.Model):
    """Track admin commission earnings from supplier products"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Withdrawal'),
        ('withdrawn', 'Withdrawn'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name='commission_earning')
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='order_commissions_earned'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_reference = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Commission {self.amount} from Order {self.order_item.order.order_number}"


# ============================================================
# ADDED: SupplierPayout Model (FIX FOR IMPORT ERROR)
# ============================================================

class SupplierPayout(models.Model):
    """Track supplier payouts for their products"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout_number = models.CharField(max_length=50, unique=True, editable=False)
    
    supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='supplier_payouts'
    )
    
    # Link to order item
    order_item = models.OneToOneField(
        'OrderItem', 
        on_delete=models.CASCADE, 
        related_name='supplier_payout'
    )
    
    # Amounts
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # Net amount after commission
    commission_deducted = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment details
    payment_method = models.CharField(max_length=50, default='mobile_money')
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['supplier', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Payout {self.payout_number} - {self.supplier.email} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.payout_number:
            import secrets
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(4).upper()
            self.payout_number = f"PO-{date_part}-{random_part}"
        super().save(*args, **kwargs)


class WithdrawalRequest(models.Model):
    """Admin withdrawal requests for accumulated commission"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='withdrawal_requests'
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    mobile_money_number = models.CharField(max_length=20)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reviewed_withdrawals'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    request_reference = models.CharField(max_length=100, unique=True, editable=False)
    transaction_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request_reference']),
            models.Index(fields=['admin', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.request_reference:
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(4).upper()
            self.request_reference = f"WDR-{date_part}-{random_part}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Withdrawal {self.amount} - {self.status}"
    
    def approve(self, admin_user):
        self.status = 'approved'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
    
    def reject(self, admin_user, reason):
        self.status = 'rejected'
        self.rejection_reason = reason
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
    
    def mark_completed(self, reference=''):
        self.status = 'completed'
        self.completed_at = timezone.now()
        if reference:
            self.transaction_reference = reference
        self.save()