from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from .models import (
    Cart, CartItem, Order, OrderItem, 
    PaymentTransaction, CommissionEarning, WithdrawalRequest
)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'base_price', 'final_price', 'commission_amount', 'supplier_payout_amount']
    can_delete = False
    show_change_link = True

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'customer_link', 'grand_total_display', 
        'payment_status_badge', 'order_status_badge', 'created_at'
    ]
    list_filter = ['payment_status', 'order_status', 'payment_method', 'created_at']
    search_fields = ['order_number', 'customer__email', 'customer__phone', 'shipping_phone']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'created_at')
        }),
        ('Order Totals', {
            'fields': ('subtotal_base', 'total_vat', 'grand_total')
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'shipping_city', 'shipping_phone', 'shipping_notes')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'payment_status', 'payment_reference', 'paid_at')
        }),
        ('Order Status', {
            'fields': ('order_status', 'tracking_number', 'estimated_delivery', 'delivered_at')
        }),
    )
    
    def customer_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.email)
    customer_link.short_description = 'Customer'
    
    def grand_total_display(self, obj):
        return format_html('<strong>{:,.0f} FRW</strong>', obj.grand_total)
    grand_total_display.short_description = 'Total'
    
    def payment_status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'simulated': '#17a2b8',
            'paid': '#28a745',
            'failed': '#dc3545',
            'refunded': '#6c757d',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.payment_status, '#6c757d'),
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment Status'
    
    def order_status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'paid': '#17a2b8',
            'processing': '#17a2b8',
            'shipped': '#28a745',
            'delivered': '#28a745',
            'cancelled': '#dc3545',
            'refunded': '#6c757d',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.order_status, '#6c757d'),
            obj.get_order_status_display()
        )
    order_status_badge.short_description = 'Order Status'
    
    actions = ['mark_as_paid', 'mark_as_shipped', 'mark_as_delivered']
    
    def mark_as_paid(self, request, queryset):
        queryset.update(payment_status='paid', paid_at=timezone.now())
        self.message_user(request, f'{queryset.count()} orders marked as paid.')
    mark_as_paid.short_description = 'Mark selected orders as paid'
    
    def mark_as_shipped(self, request, queryset):
        queryset.update(order_status='shipped')
        self.message_user(request, f'{queryset.count()} orders marked as shipped.')
    mark_as_shipped.short_description = 'Mark selected orders as shipped'
    
    def mark_as_delivered(self, request, queryset):
        queryset.update(order_status='delivered', delivered_at=timezone.now())
        self.message_user(request, f'{queryset.count()} orders marked as delivered.')
    mark_as_delivered.short_description = 'Mark selected orders as delivered'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'order_link', 'product_link', 'quantity', 
        'final_price_display', 'is_supplier_product', 'commission_display'
    ]
    list_filter = ['is_supplier_product', 'status']
    search_fields = ['order__order_number', 'product__name']
    readonly_fields = ['commission_amount', 'supplier_payout_amount']
    
    def order_link(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'
    
    def product_link(self, obj):
        url = reverse('admin:products_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'
    
    def final_price_display(self, obj):
        return format_html('{:,.0f} FRW', obj.get_total_final_price())
    final_price_display.short_description = 'Total'
    
    def commission_display(self, obj):
        if obj.is_supplier_product:
            return format_html('<span style="color: #dc3545;">{:,.0f} FRW</span>', obj.commission_amount)
        return '-'
    commission_display.short_description = 'Commission'


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'order_link', 'amount_display', 
        'payment_method', 'status_badge', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'provider', 'created_at']
    search_fields = ['transaction_id', 'order__order_number', 'customer__email']
    readonly_fields = ['transaction_id', 'created_at']
    
    fieldsets = (
        ('Transaction Info', {
            'fields': ('transaction_id', 'order', 'customer', 'amount', 'currency')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'provider', 'mobile_money_number', 'provider_transaction_id')
        }),
        ('Status', {
            'fields': ('status', 'status_message', 'created_at')
        }),
        ('Breakdown', {
            'fields': ('subtotal', 'vat_amount', 'commission_amount', 'supplier_payout', 'platform_fee')
        }),
    )
    
    def order_link(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'
    
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
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(CommissionEarning)
class CommissionEarningAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order_item_link', 'amount_display', 
        'admin', 'status_badge', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['admin__email', 'order_item__order__order_number']
    readonly_fields = ['id', 'created_at', 'withdrawn_at']
    
    fieldsets = (
        ('Commission Info', {
            'fields': ('order_item', 'admin', 'amount')
        }),
        ('Status', {
            'fields': ('status', 'withdrawn_at', 'withdrawal_reference')
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
    
    def status_badge(self, obj):
        color = '#dc3545' if obj.status == 'pending' else '#28a745'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
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
    search_fields = ['admin__email', 'mobile_money_number']
    readonly_fields = ['id', 'created_at']
    
    fieldsets = (
        ('Request Info', {
            'fields': ('admin', 'status')
        }),
        ('Amount Details', {
            'fields': ('amount',)
        }),
        ('Payment Details', {
            'fields': ('mobile_money_number', 'notes')
        }),
        ('Processing', {
            'fields': ('reviewed_by', 'rejection_reason')  # ← Removed duplicate 'notes'
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
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer_link', 'get_total_items', 'get_grand_total', 'updated_at']
    search_fields = ['customer__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def customer_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.customer.id])
        return format_html('<a href="{}">{}</a>', url, obj.customer.email)
    customer_link.short_description = 'Customer'
    
    def get_total_items(self, obj):
        return obj.get_total_items()
    get_total_items.short_description = 'Total Items'
    
    def get_grand_total(self, obj):
        return format_html('{:,.0f} FRW', obj.get_grand_total())
    get_grand_total.short_description = 'Total'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart_link', 'product_link', 'quantity', 'added_at']
    list_filter = ['added_at']
    search_fields = ['cart__customer__email', 'product__name']
    readonly_fields = ['id', 'added_at', 'updated_at']
    
    def cart_link(self, obj):
        url = reverse('admin:orders_cart_change', args=[obj.cart.id])
        return format_html('<a href="{}">Cart #{}</a>', url, obj.cart.id)
    cart_link.short_description = 'Cart'
    
    def product_link(self, obj):
        url = reverse('admin:products_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'