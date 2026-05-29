from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from ..models import Notification, NotificationPreference, NotificationTemplate

class NotificationService:
    """Service for sending notifications"""
    
    @classmethod
    def create_notification(cls, user, title, message, notification_type='system', 
                           priority='medium', link='', action_text='View Details'):
        """Create a notification"""
        
        # Check if user wants this type
        if hasattr(user, 'notification_prefs'):
            prefs = user.notification_prefs
            should_send_map = {
                'order': prefs.order_notifications,
                'payment': prefs.payment_notifications,
                'product': prefs.product_notifications,
                'supplier': prefs.supplier_notifications,
                'commission': prefs.commission_notifications,
                'promotion': prefs.promotional_notifications,
            }
            
            if not should_send_map.get(notification_type, True):
                return None
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            link=link,
            action_text=action_text
        )
        
        # Send email if enabled
        if hasattr(user, 'notification_prefs') and user.notification_prefs.email_enabled:
            cls.send_email_notification(notification)
        
        return notification
    
    @classmethod
    def send_email_notification(cls, notification):
        """Send email notification"""
        
        if notification.email_sent:
            return
        
        # Get template
        template_name = f"notifications/emails/{notification.notification_type}.html"
        
        context = {
            'user': notification.user,
            'notification': notification,
            'site_name': 'HerosTechnology',
            'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000',
        }
        
        try:
            html_message = render_to_string(template_name, context)
            plain_message = f"{notification.title}\n\n{notification.message}\n\nView: {notification.link if notification.link else settings.SITE_URL}"
            
            send_mail(
                subject=f"HerosTechnology - {notification.title}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.user.email],
                html_message=html_message,
                fail_silently=True,
            )
            
            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save()
            
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    @classmethod
    def mark_all_as_read(cls, user):
        """Mark all user notifications as read"""
        Notification.objects.filter(user=user, is_read=False).update(is_read=True, read_at=timezone.now())
    
    @classmethod
    def get_unread_count(cls, user):
        """Get unread notification count"""
        return Notification.objects.filter(user=user, is_read=False).count()
    
    @classmethod
    def send_bulk_notification(cls, users, title, message, notification_type='system', **kwargs):
        """Send notification to multiple users"""
        notifications = []
        for user in users:
            notification = cls.create_notification(user, title, message, notification_type, **kwargs)
            if notification:
                notifications.append(notification)
        return notifications