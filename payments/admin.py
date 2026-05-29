from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    PaymentTransaction, CommissionRecord, SupplierPayout, 
    WithdrawalRequest, PaymentMethod, PaymentWebhookLog
)

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'order_link', 'customer_link', 
        'amount_display', 'payment_method', 'status_badge', 'initiated_at'
    ]
    list_filter = ['status', 'payment_method', 'provider']
    search_fields = ['transaction_id', 'order__order_number', 'customer__email', 'mobile_money_number']
    readonly_fields = ['transaction_id', 'initiated_at', 'processing_at', 'completed_at', 'failed_at']
    date_hierarchy = 'initiated_at'
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('transaction_id', 'order', 'customer', 'amount', 'currency')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'provider', 'mobile_money_number', 'mobile_money_provider')
        }),
        ('Provider Information', {
            'fields': ('provider_transaction_id', 'provider_reference')
        }),
        ('Status Tracking', {
            'fields': ('status', 'status_message', 'initiated_at', 'processing_at', 'completed_at', 'failed_at')
        }),
        ('Breakdown', {
            'fields': ('subtotal', 'vat_amount', 'commission_amount', 'supplier_payout', 'platform_fee')
        }),
        ('Request/Response', {
            'fields': ('request_data', 'response_data', 'webhook_data'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'notes', 'retry_count', 'last_retry_at'),
            'classes': ('collapse',)
        }),
    )
    
    def order_link(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'
    
    def customer_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.email)
    customer_link.short_description = 'Customer'
    
    def amount_display(self, obj):
        return format_html('<strong>{:,.0f} FRW</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        colors = {
            'initiated': '#6c757d',
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#6c757d',
            'refunded': '#6c757d',
            'disputed': '#fd7e14',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 500;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{queryset.count()} transactions marked as completed.')
    mark_as_completed.short_description = 'Mark selected as completed'
    
    def mark_as_failed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='failed', failed_at=timezone.now(), status_message='Manually marked as failed')
        self.message_user(request, f'{queryset.count()} transactions marked as failed.')
    mark_as_failed.short_description = 'Mark selected as failed'


@admin.register(CommissionRecord)
class CommissionRecordAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order_item_link', 'amount_display', 
        'admin_link', 'status_badge', 'created_at'
    ]
    list_filter = ['is_withdrawn', 'commission_type', 'created_at']
    search_fields = ['admin__email', 'order_item__order__order_number']
    readonly_fields = ['id', 'created_at', 'withdrawn_at']
    
    fieldsets = (
        ('Commission Information', {
            'fields': ('order_item', 'commission_type', 'amount', 'rate')
        }),
        ('Admin Information', {
            'fields': ('admin',)
        }),
        ('Withdrawal Status', {
            'fields': ('is_withdrawn', 'withdrawn_at', 'withdrawal_reference')
        }),
    )
    
    def order_item_link(self, obj):
        return format_html(
            '<a href="{}">Order #{}</a>',
            reverse('admin:orders_orderitem_change', args=[obj.order_item.id]),
            obj.order_item.order.order_number
        )
    order_item_link.short_description = 'Order Item'
    
    def amount_display(self, obj):
        return format_html('<strong style="color: #28a745;">{:,.0f} FRW</strong>', obj.amount)
    amount_display.short_description = 'Commission'
    
    def admin_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.admin.id])
        return format_html('<a href="{}">{}</a>', url, obj.admin.email)
    admin_link.short_description = 'Admin'
    
    def status_badge(self, obj):
        if obj.is_withdrawn:
            return format_html('<span style="background-color: #28a745; color: white; padding: 3px 12px; border-radius: 20px; font-size: 11px;">Withdrawn</span>')
        return format_html('<span style="background-color: #dc3545; color: white; padding: 3px 12px; border-radius: 20px; font-size: 11px;">Pending</span>')
    status_badge.short_description = 'Status'


@admin.register(SupplierPayout)
class SupplierPayoutAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'supplier_link', 'net_amount_display', 
        'status_badge', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['supplier__email', 'provider_reference']
    readonly_fields = ['id', 'created_at', 'processed_at', 'completed_at']
    
    fieldsets = (
        ('Payout Information', {
            'fields': ('supplier', 'status')
        }),
        ('Amount Details', {
            'fields': ('amount', 'commission_deducted', 'net_amount')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Payment Details', {
            'fields': ('payout_method', 'mobile_money_number', 'bank_account', 'provider_reference')
        }),
        ('Processing', {
            'fields': ('processed_by', 'processed_at', 'completed_at', 'failure_reason', 'notes')
        }),
    )
    
    def supplier_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.supplier.id])
        return format_html('<a href="{}">{}</a>', url, obj.supplier.email)
    supplier_link.short_description = 'Supplier'
    
    def net_amount_display(self, obj):
        return format_html('<strong>{:,.0f} FRW</strong>', obj.net_amount)
    net_amount_display.short_description = 'Net Amount'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545',
            'on_hold': '#fd7e14',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 12px; border-radius: 20px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'admin_link', 'amount_display', 
        'status_badge', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['admin__email', 'mobile_money_number', 'transaction_reference']
    readonly_fields = ['id', 'created_at', 'reviewed_at', 'processed_at', 'completed_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('admin', 'status')
        }),
        ('Amount Details', {
            'fields': ('amount',)
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'mobile_money_number', 'account_name', 'transaction_reference')
        }),
        ('Processing', {
            'fields': ('reviewed_by', 'reviewed_at', 'processed_at', 'completed_at', 'rejection_reason', 'notes')
        }),
    )
    
    def admin_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.admin.id])
        return format_html('<a href="{}">{}</a>', url, obj.admin.email)
    admin_link.short_description = 'Admin'
    
    def amount_display(self, obj):
        return format_html('<strong style="color: #dc3545;">{:,.0f} FRW</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#17a2b8',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'rejected': '#dc3545',
            'cancelled': '#6c757d',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 12px; border-radius: 20px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='approved', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f'{queryset.count()} withdrawal requests approved.')
    approve_requests.short_description = 'Approve selected requests'
    
    def reject_requests(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='rejected', reviewed_by=request.user, reviewed_at=timezone.now(), rejection_reason='Rejected via admin action')
        self.message_user(request, f'{queryset.count()} withdrawal requests rejected.')
    reject_requests.short_description = 'Reject selected requests'


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active_badge', 'display_order', 'min_amount']
    list_filter = ['is_active', 'fee_type']
    search_fields = ['name', 'code']
    list_editable = ['display_order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'icon', 'description', 'is_active', 'display_order')
        }),
        ('Amount Limits', {
            'fields': ('min_amount', 'max_amount')
        }),
        ('Fee Configuration', {
            'fields': ('processing_fee', 'fee_type')
        }),
        ('API Configuration', {
            'fields': ('api_config',),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28a745;">✓ Active</span>')
        return format_html('<span style="color: #dc3545;">✗ Inactive</span>')
    is_active_badge.short_description = 'Status'


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ['provider', 'event_type', 'processed_badge', 'transaction_link', 'received_at']
    list_filter = ['provider', 'processed']
    search_fields = ['provider', 'event_type']
    readonly_fields = ['received_at', 'processed_at']
    
    fieldsets = (
        ('Webhook Information', {
            'fields': ('provider', 'event_type', 'processed')
        }),
        ('Data', {
            'fields': ('payload', 'headers')
        }),
        ('Processing', {
            'fields': ('processed_at', 'error_message')
        }),
        ('Related', {
            'fields': ('transaction',)
        }),
    )
    
    def processed_badge(self, obj):
        if obj.processed:
            return format_html('<span style="color: #28a745;">✓ Processed</span>')
        return format_html('<span style="color: #dc3545;">✗ Pending</span>')
    processed_badge.short_description = 'Processed'
    
    def transaction_link(self, obj):
        if obj.transaction:
            return format_html('<a href="/admin/payments/paymenttransaction/{}/change/">{}</a>', obj.transaction.id, obj.transaction.transaction_id)
        return '-'
    transaction_link.short_description = 'Transaction'
    
    def has_add_permission(self, request):
        return False