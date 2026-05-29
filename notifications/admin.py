from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Notification, NotificationPreference, NotificationTemplate

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user_link', 'notification_type_badge', 
        'priority_badge', 'is_read', 'is_read_badge', 'created_at'
    ]
    list_filter = ['notification_type', 'priority', 'is_read', 'email_sent', 'created_at']
    search_fields = ['title', 'message', 'user__email']
    readonly_fields = ['created_at', 'read_at', 'email_sent_at']
    list_editable = []  # Removed 'is_read' from list_editable
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('user', 'title', 'message', 'notification_type', 'priority')
        }),
        ('Action Link', {
            'fields': ('link', 'action_text')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'email_sent', 'email_sent_at', 'sms_sent')
        }),
        ('Icon', {
            'fields': ('icon',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
    user_link.short_description = 'User'
    
    def notification_type_badge(self, obj):
        icons = {
            'order': '🛒',
            'payment': '💳',
            'product': '📦',
            'supplier': '🏪',
            'commission': '💰',
            'payout': '💵',
            'system': '⚙️',
            'alert': '⚠️',
            'promotion': '🎉',
            'reminder': '🔔',
        }
        icon = icons.get(obj.notification_type, '📧')
        return format_html('{} {}', icon, obj.get_notification_type_display())
    notification_type_badge.short_description = 'Type'
    
    def priority_badge(self, obj):
        colors = {'low': '#28a745', 'medium': '#ffc107', 'high': '#fd7e14', 'urgent': '#dc3545'}
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.priority, '#6c757d'),
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html('<span style="color: #28a745;">✓ Read</span>')
        return format_html('<span style="color: #dc3545;">● Unread</span>')
    is_read_badge.short_description = 'Status Badge'
    
    actions = ['mark_as_read', 'mark_as_unread', 'resend_emails']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'{queryset.count()} notifications marked as read.')
    mark_as_read.short_description = 'Mark selected as read'
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False, read_at=None)
        self.message_user(request, f'{queryset.count()} notifications marked as unread.')
    mark_as_unread.short_description = 'Mark selected as unread'
    
    def resend_emails(self, request, queryset):
        for notification in queryset.filter(email_sent=False):
            from .utils.notification_service import NotificationService
            NotificationService.send_email_notification(notification)
        self.message_user(request, f'Emails resent for {queryset.count()} notifications.')
    resend_emails.short_description = 'Resend email notifications'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'email_enabled_badge', 'push_enabled_badge', 
        'order_notif', 'payment_notif', 'product_notif'
    ]
    list_filter = ['email_enabled', 'push_enabled', 'sms_enabled']
    search_fields = ['user__email']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Channel Preferences', {
            'fields': ('email_enabled', 'push_enabled', 'sms_enabled')
        }),
        ('Notification Types', {
            'fields': (
                'order_notifications', 'payment_notifications', 'product_notifications',
                'supplier_notifications', 'commission_notifications', 'promotional_notifications'
            )
        }),
    )
    
    def email_enabled_badge(self, obj):
        return '✓' if obj.email_enabled else '✗'
    email_enabled_badge.short_description = 'Email'
    
    def push_enabled_badge(self, obj):
        return '✓' if obj.push_enabled else '✗'
    push_enabled_badge.short_description = 'Push'
    
    def order_notif(self, obj):
        return '✓' if obj.order_notifications else '✗'
    order_notif.short_description = 'Orders'
    
    def payment_notif(self, obj):
        return '✓' if obj.payment_notifications else '✗'
    payment_notif.short_description = 'Payments'
    
    def product_notif(self, obj):
        return '✓' if obj.product_notifications else '✗'
    product_notif.short_description = 'Products'


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'subject', 'description']
    list_editable = ['is_active']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'subject', 'description', 'is_active')
        }),
        ('Template Content', {
            'fields': ('template',)
        }),
    )