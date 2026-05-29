from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .services.payment_gateway import PaymentGateway
from dashboard.utils.notifications import NotificationManager

@receiver(post_save, sender=Order)
def order_paid_notification(sender, instance, created, **kwargs):
    """Send notification when order is paid"""
    if instance.payment_status in ['simulated', 'paid'] and not created:
        # Notify admin
        from accounts.models import User
        admins = User.objects.filter(role='admin')
        for admin in admins:
            NotificationManager.create_notification(
                user=admin,
                title=f"Order Paid: #{instance.order_number}",
                message=f"Order {instance.order_number} has been paid. Amount: {instance.grand_total} FRW",
                notification_type='order',
                priority='high',
                link=f'/dashboard/admin/orders/{instance.id}/'
            )