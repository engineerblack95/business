from django.contrib import admin
from django.utils.html import format_html
from .models import DailySalesReport, PageView, ConversionTracking, SearchAnalytics

@admin.register(DailySalesReport)
class DailySalesReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_date', 'total_orders', 'total_revenue_display', 
        'average_order_value_display', 'new_customers', 'total_commission_display'
    ]
    list_filter = ['report_date']
    search_fields = ['report_date']
    date_hierarchy = 'report_date'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Report Date', {
            'fields': ('report_date',)
        }),
        ('Sales Metrics', {
            'fields': ('total_orders', 'total_revenue', 'total_items_sold', 'average_order_value')
        }),
        ('Customer Metrics', {
            'fields': ('new_customers', 'returning_customers')
        }),
        ('Product Metrics', {
            'fields': ('new_products', 'products_sold')
        }),
        ('Financial Metrics', {
            'fields': ('total_commission',)
        }),
    )
    
    def total_revenue_display(self, obj):
        return format_html('<strong>{:,.0f} FRW</strong>', obj.total_revenue)
    total_revenue_display.short_description = 'Revenue'
    
    def average_order_value_display(self, obj):
        return format_html('{:,.0f} FRW', obj.average_order_value)
    average_order_value_display.short_description = 'Avg Order'
    
    def total_commission_display(self, obj):
        return format_html('<span style="color: #dc3545;">{:,.0f} FRW</span>', obj.total_commission)
    total_commission_display.short_description = 'Commission'
    
    def has_add_permission(self, request):
        return False


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ['page_type', 'page_url_short', 'user_link', 'ip_address', 'time_spent', 'created_at']
    list_filter = ['page_type', 'created_at']
    search_fields = ['page_url', 'session_key', 'ip_address']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def page_url_short(self, obj):
        return obj.page_url[:80] + ('...' if len(obj.page_url) > 80 else '')
    page_url_short.short_description = 'Page URL'
    
    def user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
        return 'Anonymous'
    user_link.short_description = 'User'
    
    def has_add_permission(self, request):
        return False


@admin.register(ConversionTracking)
class ConversionTrackingAdmin(admin.ModelAdmin):
    list_display = ['session_key', 'stage_badge', 'user_link', 'product_link', 'value_display', 'created_at']
    list_filter = ['stage', 'created_at']
    search_fields = ['session_key', 'user__email']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def stage_badge(self, obj):
        stages = {
            'visit': '👁️',
            'view_product': '📱',
            'add_to_cart': '🛒',
            'initiate_checkout': '📝',
            'purchase': '✅',
        }
        icon = stages.get(obj.stage, '📊')
        return format_html('{} {}', icon, obj.get_stage_display())
    stage_badge.short_description = 'Stage'
    
    def user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
        return 'Anonymous'
    user_link.short_description = 'User'
    
    def product_link(self, obj):
        if obj.product:
            return format_html('<a href="/admin/products/product/{}/change/">{}</a>', obj.product.id, obj.product.name)
        return '-'
    product_link.short_description = 'Product'
    
    def value_display(self, obj):
        if obj.value:
            return format_html('{:,.0f} FRW', obj.value)
        return '-'
    value_display.short_description = 'Value'
    
    def has_add_permission(self, request):
        return False


@admin.register(SearchAnalytics)
class SearchAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'search_term', 'results_count', 'clicked_badge', 
        'user_link', 'ip_address', 'created_at'
    ]
    list_filter = ['clicked_result', 'created_at']
    search_fields = ['search_term', 'session_key', 'ip_address']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def clicked_badge(self, obj):
        if obj.clicked_result:
            return format_html('<span style="color: #28a745;">✓ Clicked</span>')
        return format_html('<span style="color: #dc3545;">✗ No Click</span>')
    clicked_badge.short_description = 'Result Clicked'
    
    def user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
        return 'Anonymous'
    user_link.short_description = 'User'
    
    def has_add_permission(self, request):
        return False