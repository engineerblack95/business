from .models import UserLoginHistory

def notifications_context(request):
    """Add notifications to all templates"""
    notifications = []
    if request.user.is_authenticated and request.user.role == 'admin':
        # Add admin notifications logic here
        notifications = []
    
    return {
        'notifications': notifications,
        'user_role': request.user.role if request.user.is_authenticated else None,
    }


def site_settings(request):
    """Add site-wide settings to all templates"""
    return {
        'site_name': 'HerosTechnology',
        'site_tagline': 'Your Trusted Electronics Marketplace',
        'site_email': 'support@herostechnology.com',
        'site_phone': '+250 788 123 456',
    }
    