from django.utils import timezone
from .models import UserLoginHistory

class RoleBasedAccessMiddleware:
    """Middleware to restrict access based on user role"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Define URL patterns and their allowed roles
        role_restrictions = {
            '/dashboard/admin/': ['admin'],
            '/dashboard/supplier/': ['admin', 'supplier'],
            '/dashboard/team/': ['admin', 'team_member'],
            '/dashboard/customer/': ['admin', 'customer', 'supplier', 'team_member'],
            '/products/manage/': ['admin', 'supplier'],
            '/products/approve/': ['admin'],
            '/suppliers/approve/': ['admin'],
            '/commission/withdraw/': ['admin'],
        }
        
        if request.user.is_authenticated:
            path = request.path_info
            for restricted_path, allowed_roles in role_restrictions.items():
                if path.startswith(restricted_path):
                    if request.user.role not in allowed_roles:
                        from django.shortcuts import redirect
                        from django.contrib import messages
                        messages.error(request, 'Access denied for your role.')
                        return redirect('dashboard:home')
        
        return None


class LoginLoggingMiddleware:
    """Ensure login history is updated on logout"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response