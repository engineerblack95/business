from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserLoginHistory
from .forms import UserCreationForm, UserChangeForm

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    model = User
    list_display = ['email', 'phone', 'full_name', 'role', 'is_active', 'is_verified', 'date_joined']
    list_filter = ['role', 'is_active', 'is_verified', 'is_approved_supplier']
    search_fields = ['email', 'phone', 'full_name', 'business_name']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('email', 'phone', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'business_name', 'tax_id')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 
                                   'is_verified', 'is_approved_supplier', 'team_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone', 'full_name', 'password1', 'password2', 'role'),
        }),
    )


@admin.register(UserLoginHistory)
class UserLoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'login_time', 'logout_time', 'ip_address', 'device_type', 'get_location_display']
    list_filter = ['device_type', 'os_type', 'login_time']
    search_fields = ['user__email', 'ip_address', 'location_country', 'location_city']
    readonly_fields = ['login_time']
    
    def get_location_display(self, obj):
        return obj.get_location_display()
    get_location_display.short_description = 'Location'