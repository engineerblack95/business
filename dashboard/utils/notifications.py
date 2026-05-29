# FIXED: Import from dashboard.models instead of notifications.models
from dashboard.models import Notification  # <-- CHANGE THIS LINE
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


class NotificationManager:
    """Manage system notifications"""
    
    @classmethod
    def send_notification(cls, user, title, message, notification_type='system', 
                         priority='medium', link='', send_email=False):
        """Send notification to user"""
        
        # Create in-app notification
        notification = Notification.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            link=link
        )
        
        # Send email if requested
        if send_email:
            try:
                if hasattr(user, 'dashboard_prefs') and user.dashboard_prefs.email_notifications:
                    cls.send_email_notification(user, title, message, link)
            except Exception:
                cls.send_email_notification(user, title, message, link)
        
        return notification
    
    @classmethod
    def send_email_notification(cls, user, title, message, link=''):
        """Send email notification"""
        
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        context = {
            'user': user,
            'title': title,
            'message': message,
            'link': link,
            'site_name': 'HerosTechnology',
            'site_url': site_url,
        }
        
        try:
            html_message = render_to_string('dashboard/emails/notification.html', context)
            plain_message = f"{title}\n\n{message}\n\nView: {link if link else site_url}"
            
            send_mail(
                subject=f"HerosTechnology - {title}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Email sending failed: {e}")
    
    @classmethod
    def create_notification(cls, user, title, message, notification_type='system', 
                           priority='medium', link=''):
        """Create notification without sending email"""
        return cls.send_notification(user, title, message, notification_type, priority, link, send_email=False)
    
    @classmethod
    def notify_new_supplier_application(cls, admin_user, applicant_email):
        """Notify admin about new supplier application"""
        cls.send_notification(
            user=admin_user,
            title="New Supplier Application",
            message=f"{applicant_email} has applied to become a supplier. Please review their application.",
            notification_type='supplier',
            priority='high',
            link='/dashboard/admin/suppliers/?pending=true'
        )
    
    @classmethod
    def notify_supplier_approved(cls, supplier):
        """Notify supplier when their application is approved"""
        cls.send_notification(
            user=supplier,
            title="Supplier Application Approved! 🎉",
            message="Congratulations! Your supplier application has been approved. You can now start adding products.",
            notification_type='supplier',
            priority='high',
            link='/dashboard/supplier/'
        )
    
    @classmethod
    def notify_supplier_rejected(cls, supplier, reason):
        """Notify supplier when their application is rejected"""
        cls.send_notification(
            user=supplier,
            title="Supplier Application Update",
            message=f"Your supplier application has been reviewed. Unfortunately, it was not approved at this time.\nReason: {reason}",
            notification_type='supplier',
            priority='medium',
            link='/suppliers/apply/'
        )
    
    @classmethod
    def notify_new_product_pending(cls, admin_user, product_name, supplier_name):
        """Notify admin about new product pending approval"""
        cls.send_notification(
            user=admin_user,
            title="New Product Pending Approval",
            message=f"{supplier_name} has submitted a new product '{product_name}' for approval.",
            notification_type='product',
            priority='high',
            link='/products/admin/approve/'
        )
    
    @classmethod
    def notify_product_approved(cls, product):
        """Notify supplier when product is approved"""
        if product.is_supplier_product:
            cls.send_notification(
                user=product.owner,
                title=f"Product Approved: {product.name}",
                message=f"Your product '{product.name}' has been approved and is now live on the platform.",
                notification_type='product',
                priority='medium',
                link=f'/products/{product.slug}/'
            )
    
    @classmethod
    def notify_product_rejected(cls, product, reason):
        """Notify supplier when product is rejected"""
        if product.is_supplier_product:
            cls.send_notification(
                user=product.owner,
                title=f"Product Rejected: {product.name}",
                message=f"Your product '{product.name}' was rejected. Reason: {reason}",
                notification_type='product',
                priority='high',
                link=f'/dashboard/supplier/products/'
            )
    
    @classmethod
    def notify_new_order(cls, order):
        """Notify admin about new order"""
        from accounts.models import User
        
        admins = User.objects.filter(role='admin')
        for admin in admins:
            cls.send_notification(
                user=admin,
                title=f"New Order #{order.order_number}",
                message=f"Order #{order.order_number} has been placed. Total: {order.grand_total} FRW",
                notification_type='order',
                priority='high',
                link=f'/dashboard/admin/orders/{order.id}/'
            )
        
        # Notify suppliers if their products are in the order
        suppliers = set()
        for item in order.items.filter(is_supplier_product=True):
            supplier = item.product.owner
            if supplier not in suppliers:
                suppliers.add(supplier)
                cls.send_notification(
                    user=supplier,
                    title=f"New Order for Your Product",
                    message=f"You have received an order for {item.product.name}. Order: #{order.order_number}",
                    notification_type='order',
                    priority='high',
                    link=f'/dashboard/supplier/orders/'
                )
    
    @classmethod
    def notify_low_stock(cls, product):
        """Notify supplier about low stock"""
        if product.is_supplier_product and product.is_low_stock():
            cls.send_notification(
                user=product.owner,
                title=f"Low Stock Alert: {product.name}",
                message=f"Your product '{product.name}' has only {product.exact_quantity} units remaining.",
                notification_type='alert',
                priority='high',
                link=f'/dashboard/supplier/products/{product.id}/stock/'
            )