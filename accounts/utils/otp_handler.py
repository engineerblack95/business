from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import os
import logging

logger = logging.getLogger(__name__)

class OTPHandler:
    """Handle OTP generation and sending with Render compatibility"""
    
    @staticmethod
    def send_otp_email(user, otp_code, purpose='login'):
        """Send OTP via email - with fallback for Render"""
        
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
        
        # Check if running on Render
        on_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', False)
        
        try:
            # Attempt to send real email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            # Log success
            print(f"✅ OTP email sent successfully to {user.email}")
            return True
            
        except Exception as e:
            # Log the error
            error_msg = f"❌ Failed to send OTP email to {user.email}: {str(e)}"
            print(error_msg)
            logger.error(error_msg)
            
            # On Render, print OTP to console for debugging
            if on_render:
                print(f"\n{'='*60}")
                print(f"🔐 DEMO MODE - OTP for {user.email}")
                print(f"📧 Purpose: {purpose}")
                print(f"🔑 OTP Code: {otp_code}")
                print(f"⏰ Valid for: {context['expiry_minutes']} minutes")
                print(f"{'='*60}\n")
                
                # Also try to store OTP in a way that views can access it
                # This will be picked up by the views.py debug mode
                return False
            else:
                # Local development - re-raise the exception
                raise e
    
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
        
        # Check if running on Render
        on_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', False)
        
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            print(f"✅ Welcome email sent successfully to {user.email}")
            return True
            
        except Exception as e:
            error_msg = f"❌ Failed to send welcome email to {user.email}: {str(e)}"
            print(error_msg)
            logger.error(error_msg)
            
            if on_render:
                print(f"📝 Welcome email would be sent to: {user.email}")
                return False
            else:
                raise e