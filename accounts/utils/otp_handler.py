from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

class OTPHandler:
    """Handle OTP generation and sending"""
    
    @staticmethod
    def send_otp_email(user, otp_code, purpose='login'):
        """Send OTP via email"""
        
        if purpose == 'registration':
            subject = 'Welcome to HerosTechnology - Verify Your Email'
            template = 'accounts/emails/registration_otp.html'
        elif purpose == 'login':
            subject = 'HerosTechnology - Login Verification Code'
            template = 'accounts/emails/login_otp.html'
        else:
            subject = 'HerosTechnology - Verification Code'
            template = 'accounts/emails/verification_otp.html'
        
        context = {
            'user': user,
            'otp_code': otp_code,
            'expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 5),
            'site_name': 'HerosTechnology',
        }
        
        html_message = render_to_string(template, context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
    
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email after successful registration"""
        subject = 'Welcome to HerosTechnology!'
        template = 'accounts/emails/welcome.html'
        
        context = {
            'user': user,
            'site_name': 'HerosTechnology',
            'login_url': '/accounts/login/',
        }
        
        html_message = render_to_string(template, context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )