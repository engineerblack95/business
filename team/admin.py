from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from .models import TeamMember, TeamTask, TeamActivity
from accounts.models import User


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'position_display', 'email', 
        'display_order', 'is_active', 'featured', 'profile_preview', 'user_link'
    ]
    list_filter = ['position', 'is_active', 'featured', 'joined_at']
    search_fields = ['full_name', 'email', 'bio', 'user__email']
    list_editable = ['display_order', 'is_active', 'featured']
    readonly_fields = ['tasks_completed', 'customer_satisfaction', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'full_name', 'position', 'custom_position', 'email', 'phone', 'profile_image')
        }),
        ('Biography', {
            'fields': ('bio', 'expertise', 'achievements')
        }),
        ('Social Media', {
            'fields': ('linkedin', 'twitter', 'facebook', 'instagram')
        }),
        ('Display Settings', {
            'fields': ('display_order', 'is_active', 'featured')
        }),
        ('Statistics', {
            'fields': ('tasks_completed', 'customer_satisfaction'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('joined_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def position_display(self, obj):
        return obj.get_display_position()
    position_display.short_description = 'Position'
    
    def profile_preview(self, obj):
        if obj.profile_image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; border-radius: 50%; object-fit: cover;" />', obj.profile_image.url)
        return '<div style="width: 50px; height: 50px; border-radius: 50%; background-color: #6c757d; display: flex; align-items: center; justify-content: center;"><span style="color: white;">📷</span></div>'
    profile_preview.short_description = 'Photo'
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.id])
            return format_html('<a href="{}">View User Account</a>', url)
        return '<span style="color: #6c757d;">No linked user</span>'
    user_link.short_description = 'Account'
    
    def save_model(self, request, obj, form, change):
        """Override save to handle User account creation/update"""
        super().save_model(request, obj, form, change)
        
        # Create or update associated User account for dashboard access
        if obj.email:
            user, created = User.objects.get_or_create(
                email=obj.email,
                defaults={
                    'full_name': obj.full_name,
                    'phone': obj.phone or '',
                    'role': 'team_member',
                    'is_active': True,
                    'team_permissions': {
                        'can_view_orders': True,
                        'can_view_products': True,
                        'can_edit_products': False,
                        'can_approve_products': False,
                        'can_manage_suppliers': False,
                        'can_view_financial': False,
                    }
                }
            )
            if not created:
                # Update existing user
                user.full_name = obj.full_name
                user.phone = obj.phone or ''
                if user.role == 'customer':
                    user.role = 'team_member'
                user.save()
            
            # Link the user back to team member
            if obj.user != user:
                obj.user = user
                obj.save()
            
            if created:
                messages.success(request, f'User account for {obj.email} created with team_member role.')
            else:
                messages.info(request, f'Linked to existing user account: {obj.email}')


@admin.register(TeamTask)
class TeamTaskAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'assigned_to_display', 'priority_badge', 
        'status_badge', 'due_date_badge', 'created_at'
    ]
    list_filter = ['priority', 'status', 'assigned_to', 'created_at']
    search_fields = ['title', 'description', 'assigned_to__email']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Task Information', {
            'fields': ('title', 'description', 'priority', 'status')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_by')
        }),
        ('Dates', {
            'fields': ('due_date', 'completed_at')
        }),
        ('Related Objects', {
            'fields': ('related_order', 'related_product', 'related_supplier')
        }),
        ('Additional Info', {
            'fields': ('notes', 'attachments')
        }),
    )
    
    def assigned_to_display(self, obj):
        if obj.assigned_to:
            url = reverse('admin:accounts_user_change', args=[obj.assigned_to.id])
            return format_html('<a href="{}">{}</a>', url, obj.assigned_to.email)
        return '<span style="color: #6c757d;">Unassigned</span>'
    assigned_to_display.short_description = 'Assigned To'
    
    def priority_badge(self, obj):
        colors = {'low': '#28a745', 'medium': '#ffc107', 'high': '#fd7e14', 'urgent': '#dc3545'}
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.priority, '#6c757d'),
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'in_progress': '#17a2b8',
            'review': '#fd7e14',
            'completed': '#28a745',
            'cancelled': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def due_date_badge(self, obj):
        from django.utils import timezone
        
        if not obj.due_date:
            return '<span style="background-color: #6c757d; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">No due date</span>'
        
        if obj.status == 'completed':
            color = '#28a745'
        elif obj.due_date < timezone.now():
            color = '#dc3545'
        elif obj.due_date < timezone.now() + timezone.timedelta(days=2):
            color = '#ffc107'
        else:
            color = '#6c757d'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.due_date.strftime('%Y-%m-%d %H:%M')
        )
    due_date_badge.short_description = 'Due Date'


@admin.register(TeamActivity)
class TeamActivityAdmin(admin.ModelAdmin):
    list_display = ['team_member_display', 'activity_type', 'description_preview', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['team_member__email', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def team_member_display(self, obj):
        if obj.team_member:
            url = reverse('admin:accounts_user_change', args=[obj.team_member.id])
            return format_html('<a href="{}">{}</a>', url, obj.team_member.email)
        return '<span style="color: #6c757d;">Unknown</span>'
    team_member_display.short_description = 'Team Member'
    
    def description_preview(self, obj):
        if len(obj.description) > 100:
            return obj.description[:100] + '...'
        return obj.description
    description_preview.short_description = 'Description'