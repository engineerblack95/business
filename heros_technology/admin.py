from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _

class HerosTechnologyAdminSite(AdminSite):
    site_title = _('HerosTechnology Admin')
    site_header = _('HerosTechnology Administration')
    index_title = _('Site Administration')
    
    def get_app_list(self, request):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_list = super().get_app_list(request)
        
        # Custom ordering of apps
        app_order = ['accounts', 'suppliers', 'products', 'orders', 'payments', 
                    'dashboard', 'team', 'analytics', 'notifications']
        
        # Sort apps according to custom order
        app_dict = {app['app_label']: app for app in app_list}
        ordered_app_list = []
        for app_label in app_order:
            if app_label in app_dict:
                ordered_app_list.append(app_dict[app_label])
        
        # Add any remaining apps
        for app in app_list:
            if app['app_label'] not in app_order:
                ordered_app_list.append(app)
        
        return ordered_app_list


# Unregister the default admin site and register our custom one
admin_site = HerosTechnologyAdminSite(name='myadmin')

# Register all models with the custom admin site
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import GroupAdmin, UserAdmin

admin_site.register(Group, GroupAdmin)
admin_site.register(User, UserAdmin)

# Override the default admin
admin.site = admin_site