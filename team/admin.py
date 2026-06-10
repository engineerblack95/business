from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django import forms
from django.core.exceptions import ValidationError
from .models import TeamMember, TeamTask, TeamActivity
from accounts.models import User


class TeamMemberAdminForm(forms.ModelForm):
    """Custom form for TeamMember - User must already be registered"""
    
    # Permission fields for team member
    can_view_orders = forms.BooleanField(required=False, initial=True, label="✓ View Orders")
    can_view_products = forms.BooleanField(required=False, initial=True, label="✓ View Products")
    can_edit_products = forms.BooleanField(required=False, initial=False, label="✎ Edit Products")
    can_approve_products = forms.BooleanField(required=False, initial=False, label="✓ Approve Products")
    can_manage_suppliers = forms.BooleanField(required=False, initial=False, label="🏢 Manage Suppliers")
    can_view_logs = forms.BooleanField(required=False, initial=False, label="📋 View Activity Logs")
    can_view_financial = forms.BooleanField(required=False, initial=False, label="💰 View Financial Data")
    
    class Meta:
        model = TeamMember
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make email field required and add help text
        self.fields['email'].required = True
        self.fields['email'].help_text = "Must be an email of an already registered user on the system."
        
        # If editing existing team member, load current permissions
        if self.instance and self.instance.pk and self.instance.user:
            user = self.instance.user
            perms = user.team_permissions
            
            self.initial['can_view_orders'] = perms.get('can_view_orders', True)
            self.initial['can_view_products'] = perms.get('can_view_products', True)
            self.initial['can_edit_products'] = perms.get('can_edit_products', False)
            self.initial['can_approve_products'] = perms.get('can_approve_products', False)
            self.initial['can_manage_suppliers'] = perms.get('can_manage_suppliers', False)
            self.initial['can_view_logs'] = perms.get('can_view_logs', False)
            self.initial['can_view_financial'] = perms.get('can_view_financial', False)
            
            # Make email read-only when editing
            self.fields['email'].widget.attrs['readonly'] = True
            self.fields['email'].help_text = "Email cannot be changed after creation"
    
    def clean_email(self):
        """CRITICAL: Validate that the user already exists in the system"""
        email = self.cleaned_data.get('email')
        
        if not email:
            raise ValidationError('Email address is required.')
        
        # Check if user exists in the system
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # User does not exist - show error message
            raise ValidationError(
                f'❌ User with email "{email}" does not exist in the system.\n\n'
                f'To add this person as a team member, they must FIRST register as a customer on the website.\n\n'
                f'Please ask them to register at: /accounts/register/\n\n'
                f'After they register, you can add them as a team member.'
            )
        
        # If editing existing team member and email hasn't changed, allow it
        if self.instance and self.instance.pk and self.instance.user:
            if self.instance.user.email == email:
                return email
        
        # Check if user is already an admin (cannot be demoted)
        if user.role == 'admin':
            raise ValidationError(
                f'❌ User "{email}" is an ADMIN.\n\n'
                f'Admin users already have full system access and cannot be added as team members.'
            )
        
        # Check if user is already a supplier
        if user.role == 'supplier':
            raise ValidationError(
                f'❌ User "{email}" is already a SUPPLIER.\n\n'
                f'Suppliers have their own dashboard and cannot be added as team members.\n\n'
                f'If you want this user to be a team member, first remove their supplier status.'
            )
        
        # Check if user is already a team member
        if user.role == 'team_member':
            # Check if this team member record already exists
            if TeamMember.objects.filter(user=user).exists():
                existing = TeamMember.objects.get(user=user)
                if self.instance and self.instance.pk == existing.pk:
                    # Same record being edited - allow
                    return email
                else:
                    raise ValidationError(
                        f'⚠️ User "{email}" is already a team member!\n\n'
                        f'They are already added to the team. Please edit the existing record instead.'
                    )
        
        # User must be a customer to become team member
        if user.role != 'customer':
            raise ValidationError(
                f'User "{email}" has role "{user.role}".\n\n'
                f'Only customers can be promoted to team members.'
            )
        
        return email
    
    def save(self, commit=True):
        """Save team member and update associated user (no user creation)"""
        instance = super().save(commit=False)
        
        # Get the existing user (must exist from validation)
        email = self.cleaned_data.get('email')
        user = User.objects.get(email=email)
        
        # Link the user to team member
        instance.user = user
        
        # Update user's details from form
        if self.cleaned_data.get('full_name'):
            user.full_name = self.cleaned_data.get('full_name')
        
        if self.cleaned_data.get('phone'):
            user.phone = self.cleaned_data.get('phone')
        
        # Update user's role to team_member
        if user.role != 'team_member':
            user.role = 'team_member'
        
        # Update user's team permissions
        user.team_permissions = {
            'can_view_orders': self.cleaned_data.get('can_view_orders', True),
            'can_view_products': self.cleaned_data.get('can_view_products', True),
            'can_edit_products': self.cleaned_data.get('can_edit_products', False),
            'can_approve_products': self.cleaned_data.get('can_approve_products', False),
            'can_manage_suppliers': self.cleaned_data.get('can_manage_suppliers', False),
            'can_view_logs': self.cleaned_data.get('can_view_logs', False),
            'can_view_financial': self.cleaned_data.get('can_view_financial', False),
        }
        user.save()
        
        if commit:
            instance.save()
        
        return instance


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    form = TeamMemberAdminForm
    
    list_display = [
        'full_name', 'position_display', 'email', 
        'display_order', 'is_active', 'featured', 'user_status'
    ]
    list_filter = ['position', 'is_active', 'featured', 'joined_at']
    search_fields = ['full_name', 'email', 'bio', 'user__email', 'user__full_name']
    list_editable = ['display_order', 'is_active', 'featured']
    readonly_fields = ['tasks_completed', 'customer_satisfaction', 'created_at', 'updated_at']
    
    fieldsets = (
        ('User Account (Must be pre-registered)', {
            'fields': ('email',),
            'description': '<div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">'
                          '⚠️ <strong>Important:</strong> The user must already be registered on the website as a customer. '
                          'If the email does not exist in the system, you will get an error.</div>',
        }),
        ('Personal Information', {
            'fields': ('full_name', 'position', 'custom_position', 'phone', 'profile_image')
        }),
        ('System Permissions (Dashboard Access)', {
            'fields': (
                ('can_view_orders', 'can_view_products'),
                ('can_edit_products', 'can_approve_products'),
                ('can_manage_suppliers', 'can_view_logs'),
                ('can_view_financial',),
            ),
            'description': 'Control what this team member can access in the admin dashboard',
            'classes': ('wide',),
        }),
        ('Biography & Social', {
            'fields': ('bio', 'expertise', 'achievements', 'linkedin', 'twitter', 'facebook', 'instagram')
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
    
    def user_status(self, obj):
        """Display user's registration status"""
        if obj.user:
            role = obj.user.role
            if role == 'team_member':
                return '✅ Active Team Member'
            elif role == 'customer':
                return '⚠️ Still Customer (will update on save)'
            else:
                return f'⚠️ Role: {role}'
        return '❌ User Not Found'
    user_status.short_description = 'User Status'
    
    def save_model(self, request, obj, form, change):
        """Override save to add success message"""
        try:
            super().save_model(request, obj, form, change)
            
            if obj.user:
                perm_count = len([p for p in obj.user.team_permissions.values() if p])
                if change:
                    messages.success(
                        request, 
                        f'✅ Team member "{obj.full_name}" updated successfully! '
                        f'User {obj.user.email} now has team member role with {perm_count} permissions.'
                    )
                else:
                    messages.success(
                        request, 
                        f'🎉 Team member "{obj.full_name}" added successfully! '
                        f'User {obj.user.email} has been promoted to team member with {perm_count} permissions.'
                    )
        except Exception as e:
            messages.error(request, f'Error saving team member: {str(e)}')
    
    def delete_model(self, request, obj):
        """When deleting team member, revert user role to customer"""
        user = obj.user
        email = obj.email
        
        try:
            if user and user.role == 'team_member':
                # Revert to customer
                user.role = 'customer'
                user.team_permissions = {}
                user.save()
                messages.info(
                    request, 
                    f'⚠️ Team member removed. User {user.email} role reverted to customer.\n\n'
                    f'The user account remains active but can no longer access team dashboard.'
                )
            obj.delete()
            messages.success(request, f'Team member record deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting team member: {str(e)}')
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user')
    
    # Custom actions
    actions = ['grant_full_access', 'revoke_all_access', 'make_featured']
    
    def grant_full_access(self, request, queryset):
        """Grant all permissions to selected team members"""
        count = 0
        for team_member in queryset:
            try:
                if team_member.user and team_member.user.role == 'team_member':
                    team_member.user.team_permissions = {
                        'can_view_orders': True,
                        'can_view_products': True,
                        'can_edit_products': True,
                        'can_approve_products': True,
                        'can_manage_suppliers': True,
                        'can_view_logs': True,
                        'can_view_financial': True,
                    }
                    team_member.user.save()
                    count += 1
            except Exception:
                pass
        self.message_user(request, f'✅ Full access granted to {count} team member(s).')
    grant_full_access.short_description = "Grant FULL access to selected"
    
    def revoke_all_access(self, request, queryset):
        """Revoke all permissions from selected team members"""
        count = 0
        for team_member in queryset:
            try:
                if team_member.user and team_member.user.role == 'team_member':
                    team_member.user.team_permissions = {
                        'can_view_orders': False,
                        'can_view_products': False,
                        'can_edit_products': False,
                        'can_approve_products': False,
                        'can_manage_suppliers': False,
                        'can_view_logs': False,
                        'can_view_financial': False,
                    }
                    team_member.user.save()
                    count += 1
            except Exception:
                pass
        self.message_user(request, f'⚠️ All access revoked from {count} team member(s).')
    revoke_all_access.short_description = "Revoke ALL access from selected"
    
    def make_featured(self, request, queryset):
        """Mark selected team members as featured"""
        updated = queryset.update(featured=True)
        self.message_user(request, f'⭐ {updated} team member(s) marked as featured.')
    make_featured.short_description = "Mark as featured (show on homepage)"


@admin.register(TeamTask)
class TeamTaskAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'assigned_to', 'priority', 'status', 'due_date', 'created_at'
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


@admin.register(TeamActivity)
class TeamActivityAdmin(admin.ModelAdmin):
    list_display = ['team_member', 'activity_type', 'description', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['team_member__email', 'description']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False