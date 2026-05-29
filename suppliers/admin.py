from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    SupplierApplication, SupplierProfile, 
    SupplierPayoutHistory, SupplierPerformanceMetric
)

@admin.register(SupplierApplication)
class SupplierApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'application_number', 'business_name', 'supplier', 
        'status', 'get_status_badge', 'created_at'
    ]
    list_filter = ['status', 'business_type', 'created_at']
    search_fields = [
        'application_number', 'business_name', 
        'supplier__email', 'tax_id', 'registration_number'
    ]
    readonly_fields = [
        'application_number', 'created_at', 'updated_at',
        'reviewed_at', 'approved_at'
    ]
    
    fieldsets = (
        ('Application Information', {
            'fields': (
                'application_number', 'supplier', 'status',
                'business_name', 'business_type', 'tax_id', 'registration_number'
            )
        }),
        ('Contact Information', {
            'fields': ('business_phone', 'business_email', 'business_address', 'business_city', 'business_country')
        }),
        ('Business Details', {
            'fields': ('website', 'years_in_business', 'estimated_monthly_volume', 'notes')
        }),
        ('Documents', {
            'fields': ('business_license', 'id_document', 'tax_clearance', 'bank_statement', 'additional_documents')
        }),
        ('Categories', {
            'fields': ('interested_categories',)
        }),
        ('Review Information', {
            'fields': ('rejection_reason', 'additional_info_request', 'reviewed_by', 'reviewed_at', 'approved_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_status_badge(self, obj):
        status_colors = {
            'pending': '#ffc107',
            'reviewing': '#17a2b8',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'additional_info': '#6c757d',
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    get_status_badge.short_description = 'Status'
    
    actions = ['approve_applications', 'reject_applications']
    
    def approve_applications(self, request, queryset):
        for application in queryset.filter(status='pending'):
            application.approve(request.user)
        self.message_user(request, f'{queryset.count()} applications approved.')
    approve_applications.short_description = 'Approve selected applications'
    
    def reject_applications(self, request, queryset):
        for application in queryset.filter(status='pending'):
            application.reject(request.user, 'Rejected via admin action')
        self.message_user(request, f'{queryset.count()} applications rejected.')
    reject_applications.short_description = 'Reject selected applications'


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    # Use direct field names instead of custom methods
    list_display = [
        'business_name', 'supplier_link', 'verification_status', 
        'total_sales', 'average_rating', 'is_active'
    ]
    list_filter = ['verification_status', 'is_active', 'business_type', 'created_at']
    search_fields = ['business_name', 'supplier__email', 'supplier__phone']
    readonly_fields = [
        'total_sales', 'total_products_sold', 'total_products',
        'average_rating', 'total_reviews', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Business Information', {
            'fields': (
                'supplier', 'business_name', 'business_type', 
                'logo', 'cover_image', 'description'
            )
        }),
        ('Contact Details', {
            'fields': (
                'business_phone', 'business_email', 'business_address',
                'business_city', 'business_country', 'website', 'social_media'
            )
        }),
        ('Business Statistics', {
            'fields': (
                'years_in_business', 'number_of_employees',
                'total_sales', 'total_products_sold', 'total_products'
            )
        }),
        ('Performance Metrics', {
            'fields': ('average_rating', 'total_reviews', 'response_rate', 'response_time')
        }),
        ('Verification', {
            'fields': ('verification_status', 'verified_at', 'verification_documents')
        }),
        ('Payment Settings', {
            'fields': (
                'payment_method', 'mobile_money_number',
                'bank_account_name', 'bank_account_number', 'bank_name'
            )
        }),
        ('Status', {
            'fields': ('is_active', 'auto_approve_products')
        }),
    )
    
    def supplier_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.supplier.id])
        return format_html('<a href="{}">{}</a>', url, obj.supplier.email)
    supplier_link.short_description = 'Supplier'


@admin.register(SupplierPayoutHistory)
class SupplierPayoutHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'payout_number', 'supplier_link', 'net_amount', 
        'status', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['payout_number', 'supplier__email', 'transaction_reference']
    readonly_fields = ['payout_number', 'created_at']
    
    fieldsets = (
        ('Payout Information', {
            'fields': ('payout_number', 'supplier', 'status')
        }),
        ('Amount Details', {
            'fields': ('amount', 'commission_deducted', 'net_amount')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Payment Details', {
            'fields': ('payment_method', 'payment_details', 'transaction_reference')
        }),
        ('Processing', {
            'fields': ('processed_by', 'processed_at', 'completed_at', 'failure_reason', 'notes')
        }),
    )
    
    def supplier_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.supplier.id])
        return format_html('<a href="{}">{}</a>', url, obj.supplier.email)
    supplier_link.short_description = 'Supplier'


@admin.register(SupplierPerformanceMetric)
class SupplierPerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ['supplier_link', 'period_date', 'period_type', 'total_sales', 'total_orders', 'average_rating']
    list_filter = ['period_type', 'period_date']
    search_fields = ['supplier__email']
    date_hierarchy = 'period_date'
    
    def supplier_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.supplier.id])
        return format_html('<a href="{}">{}</a>', url, obj.supplier.email)
    supplier_link.short_description = 'Supplier'