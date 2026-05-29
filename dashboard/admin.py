from django.contrib import admin
from django.utils.html import format_html
from .models import UserActivityLog, DashboardPreference

# DO NOT register Notification here - it belongs to notifications app
# Only register models that belong to dashboard app

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'activity_type', 'description_preview', 
        'ip_address', 'created_at'
    ]
    list_filter = ['activity_type', 'created_at']
    search_fields = ['user__email', 'description', 'ip_address']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def user_link(self, obj):
        return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
    user_link.short_description = 'User'
    
    def description_preview(self, obj):
        return obj.description[:100] + ('...' if len(obj.description) > 100 else '')
    description_preview.short_description = 'Activity'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DashboardPreference)
class DashboardPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'email_notifications_badge', 'push_notifications_badge', 'updated_at']
    list_filter = ['theme', 'email_notifications', 'push_notifications']
    search_fields = ['user__email']
    readonly_fields = ['updated_at']
    
    def email_notifications_badge(self, obj):
        return '✓' if obj.email_notifications else '✗'
    email_notifications_badge.short_description = 'Email Notifications'
    
    def push_notifications_badge(self, obj):
        return '✓' if obj.push_notifications else '✗'
    push_notifications_badge.short_description = 'Push Notifications'