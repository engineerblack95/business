from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import secrets

class PaymentTransaction(models.Model):
    """Complete payment transaction tracking"""
    
    TRANSACTION_STATUS = [
        ('initiated', 'Initiated'),
        ('pending', 'Pending Verification'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
    ]
    
    PAYMENT_METHODS = [
        ('mobile_money_mtn', 'MTN Mobile Money'),
        ('mobile_money_airtel', 'Airtel Money'),
        ('mobile_money_tigo', 'Tigo Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Credit/Debit Card'),
        ('cash_on_delivery', 'Cash on Delivery'),
        ('wallet', 'Wallet Balance'),
    ]
    
    PROVIDERS = [
        ('mtn', 'MTN MoMo API'),
        ('airtel', 'Airtel Money API'),
        ('simulated', 'Simulated Payment'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Related order
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payment_transactions')
    
    # Customer information
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    
    # Payment details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='RWF')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHODS)
    provider = models.CharField(max_length=20, choices=PROVIDERS, default='simulated')
    
    # Mobile money specific
    mobile_money_number = models.CharField(max_length=20, blank=True)
    mobile_money_provider = models.CharField(max_length=20, blank=True)
    
    # Transaction details
    provider_transaction_id = models.CharField(max_length=100, blank=True)
    provider_reference = models.CharField(max_length=100, blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='initiated')
    status_message = models.TextField(blank=True)
    
    # Request/Response data
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    webhook_data = models.JSONField(default=dict, blank=True)
    
    # Payment breakdown
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier_payout = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    processing_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    
    # Retry information
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['customer', '-initiated_at']),
            models.Index(fields=['provider_transaction_id']),
            models.Index(fields=['status', 'initiated_at']),
            models.Index(fields=['payment_method', 'status']),
        ]
    
    def __str__(self):
        return f"Payment {self.transaction_id} - {self.amount} {self.currency} - {self.status}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            # Generate unique transaction ID
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(6).upper()
            self.transaction_id = f"TXN-{date_part}-{random_part}"
        super().save(*args, **kwargs)
    
    def mark_completed(self, provider_txn_id=None):
        """Mark transaction as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if provider_txn_id:
            self.provider_transaction_id = provider_txn_id
        self.save()
        
        # Update order payment status
        self.order.payment_status = 'paid'
        self.order.paid_at = timezone.now()
        self.order.save()
    
    def mark_failed(self, reason):
        """Mark transaction as failed"""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.status_message = reason
        self.save()
    
    def mark_refunded(self, reason=None):
        """Mark transaction as refunded"""
        self.status = 'refunded'
        if reason:
            self.status_message = reason
        self.save()
        
        # Update order
        self.order.payment_status = 'refunded'
        self.order.order_status = 'refunded'
        self.order.save()
    
    def can_retry(self):
        """Check if payment can be retried"""
        return self.status in ['failed', 'cancelled'] and self.retry_count < 3
    
    def get_payment_method_display_name(self):
        """Get display name for payment method"""
        method_names = {
            'mobile_money_mtn': 'MTN Mobile Money',
            'mobile_money_airtel': 'Airtel Money',
            'mobile_money_tigo': 'Tigo Cash',
            'bank_transfer': 'Bank Transfer',
            'card': 'Credit/Debit Card',
            'cash_on_delivery': 'Cash on Delivery',
            'wallet': 'Wallet Balance',
        }
        return method_names.get(self.payment_method, self.payment_method)


class CommissionRecord(models.Model):
    """Record of commission earnings from supplier products"""
    
    COMMISSION_TYPES = [
        ('product_sale', 'Product Sale Commission'),
        ('platform_fee', 'Platform Fee'),
        ('service_fee', 'Service Fee'),
        ('adjustment', 'Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commission_code = models.CharField(max_length=50, unique=True, editable=False)
    
    # Related objects
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='commission_records')
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.CASCADE, related_name='commissions')
    
    # Commission details
    commission_type = models.CharField(max_length=20, choices=COMMISSION_TYPES, default='product_sale')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Commission rate percentage")
    
    # Admin owner
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='commissions_earned')
    
    # Status
    is_withdrawn = models.BooleanField(default=False)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_reference = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin', 'is_withdrawn']),
            models.Index(fields=['commission_code']),
        ]
    
    def __str__(self):
        return f"Commission {self.commission_code} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.commission_code:
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(4).upper()
            self.commission_code = f"COM-{date_part}-{random_part}"
        super().save(*args, **kwargs)


class SupplierPayout(models.Model):
    """Track payouts to suppliers"""
    
    PAYOUT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('on_hold', 'On Hold'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout_code = models.CharField(max_length=50, unique=True, editable=False)
    
    # Supplier
    supplier = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='payment_supplier_payouts'  # ← FIXED: unique related_name
    )
    
    # Payout details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_deducted = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Related transactions
    order_items = models.ManyToManyField('orders.OrderItem', related_name='supplier_payouts')
    payment_transactions = models.ManyToManyField(PaymentTransaction, related_name='supplier_payouts')
    
    # Payout method
    payout_method = models.CharField(max_length=30, choices=PaymentTransaction.PAYMENT_METHODS)
    mobile_money_number = models.CharField(max_length=20, blank=True)
    bank_account = models.JSONField(default=dict, blank=True)
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS, default='pending')
    failure_reason = models.TextField(blank=True)
    
    # Processing
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='payment_processed_payouts'  # ← FIXED: unique related_name
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Provider reference
    provider_reference = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payout_code']),
            models.Index(fields=['supplier', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Payout {self.payout_code} - {self.supplier.email} - {self.net_amount}"
    
    def save(self, *args, **kwargs):
        if not self.payout_code:
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(4).upper()
            self.payout_code = f"PO-{date_part}-{random_part}"
        super().save(*args, **kwargs)
    
    def mark_completed(self, reference=''):
        """Mark payout as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if reference:
            self.provider_reference = reference
        self.save()
    
    def mark_failed(self, reason):
        """Mark payout as failed"""
        self.status = 'failed'
        self.failure_reason = reason
        self.save()


class WithdrawalRequest(models.Model):
    """Admin withdrawal requests for accumulated commission"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_code = models.CharField(max_length=50, unique=True, editable=False)
    
    # Admin user
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='payment_withdrawal_requests'  # ← FIXED: unique related_name
    )
    
    # Withdrawal details
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('1000'))])
    
    # Payment details
    payment_method = models.CharField(max_length=30, choices=PaymentTransaction.PAYMENT_METHODS, default='mobile_money_mtn')
    mobile_money_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=255, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    
    # Processing
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='payment_reviewed_withdrawals'  # ← FIXED: unique related_name
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Transaction reference
    transaction_reference = models.CharField(max_length=100, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request_code']),
            models.Index(fields=['admin', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Withdrawal {self.request_code} - {self.admin.email} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.request_code:
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = secrets.token_hex(4).upper()
            self.request_code = f"WDR-{date_part}-{random_part}"
        super().save(*args, **kwargs)
    
    def approve(self, admin_user):
        """Approve withdrawal request"""
        self.status = 'approved'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
    
    def reject(self, admin_user, reason):
        """Reject withdrawal request"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
    
    def mark_completed(self, reference=''):
        """Mark withdrawal as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if reference:
            self.transaction_reference = reference
        self.save()


class PaymentMethod(models.Model):
    """Available payment methods configuration"""
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, unique=True)
    icon = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    is_simulated = models.BooleanField(default=False, help_text="Simulated mode for development")
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    processing_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Fixed fee or percentage")
    fee_type = models.CharField(max_length=10, choices=[('fixed', 'Fixed'), ('percentage', 'Percentage')], default='fixed')
    
    # API configuration (stored encrypted in production)
    api_config = models.JSONField(default=dict, blank=True)
    
    # Display settings
    display_order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order']
    
    def __str__(self):
        return self.name
    
    def calculate_fee(self, amount):
        """Calculate processing fee for amount"""
        if self.fee_type == 'fixed':
            return self.processing_fee
        else:
            return (amount * self.processing_fee / 100).quantize(Decimal('0.01'))


class PaymentWebhookLog(models.Model):
    """Log all payment webhook calls"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)
    
    # Data
    payload = models.JSONField()
    headers = models.JSONField(default=dict)
    
    # Processing
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Related transaction
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True)
    
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-received_at']
    
    def __str__(self):
        return f"Webhook {self.provider} - {self.event_type} - {self.received_at}"