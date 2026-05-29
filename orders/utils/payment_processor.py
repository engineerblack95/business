from decimal import Decimal
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import secrets
from orders.models import PaymentTransaction, Order, CommissionEarning
from products.utils.stock_manager import StockManager


class PaymentProcessor:
    """Handle payment processing (simulated for development)"""
    
    @classmethod
    def process_simulated_payment(cls, order, mobile_money_number):
        """
        Simulate mobile money payment during development
        Returns tuple (success, transaction, message)
        """
        
        # Create transaction record
        transaction_id = f"SIM-{secrets.token_hex(8).upper()}"
        
        transaction = PaymentTransaction.objects.create(
            order=order,
            transaction_id=transaction_id,
            amount=order.grand_total,
            payment_method='mobile_money',
            status='initiated',
            provider='simulated',
            response_data={
                'mobile_money_number': mobile_money_number,
                'simulated_at': timezone.now().isoformat()
            }
        )
        
        # Simulate payment processing (always success in dev)
        # In production, you would call actual mobile money API here
        
        # Mark as successful
        transaction.status = 'success'
        transaction.completed_at = timezone.now()
        transaction.save()
        
        # Update order
        order.payment_status = 'simulated'
        order.paid_at = timezone.now()
        order.order_status = 'paid'
        order.save()
        
        # Update order items status
        for item in order.items.all():
            item.status = 'processing'
            item.save()
        
        # Create commission earnings for admin (for supplier products)
        cls.create_commission_earnings(order)
        
        # Create supplier payouts
        cls.create_supplier_payouts(order)
        
        # Send confirmation email
        cls.send_order_confirmation(order)
        
        # Send in-app notifications
        cls.send_order_notifications(order)
        
        return True, transaction, "Payment simulated successfully"
    
    @classmethod
    def send_order_notifications(cls, order):
        """Send in-app notifications for new order"""
        from accounts.models import User
        from notifications.utils.notification_service import NotificationService
        
        # Notify all admins about new order
        admins = User.objects.filter(role='admin')
        for admin in admins:
            NotificationService.create_notification(
                user=admin,
                title=f"New Order #{order.order_number}",
                message=f"A new order #{order.order_number} has been placed. Total: {order.grand_total:,.0f} FRW",
                notification_type='order',
                priority='high',
                link=f'/orders/admin/orders/'
            )
        
        # Notify suppliers for their products in the order
        suppliers_notified = set()
        for item in order.items.filter(is_supplier_product=True):
            supplier = item.product.owner
            if supplier.id not in suppliers_notified:
                suppliers_notified.add(supplier.id)
                NotificationService.create_notification(
                    user=supplier,
                    title="New Order Received! 🎉",
                    message=f"You have received a new order #{order.order_number} for your product '{item.product.name}'. Amount: {item.get_total_final_price():,.0f} FRW",
                    notification_type='order',
                    priority='high',
                    link=f'/orders/supplier/orders/'
                )
        
        # Notify the customer
        NotificationService.create_notification(
            user=order.customer,
            title=f"Order Confirmed - {order.order_number}",
            message=f"Your order #{order.order_number} has been successfully placed. Total: {order.grand_total:,.0f} FRW",
            notification_type='order',
            priority='medium',
            link=f'/orders/order/{order.id}/'
        )
    
    @classmethod
    def create_commission_earnings(cls, order):
        """Create commission earnings for admin from supplier products"""
        from accounts.models import User
        
        # Get admin users (superusers or role='admin')
        admins = User.objects.filter(role='admin')
        
        if not admins.exists():
            return
        
        admin = admins.first()  # Use first admin as default
        
        for item in order.items.filter(is_supplier_product=True):
            # Check if commission already exists
            if not hasattr(item, 'commission_earning'):
                CommissionEarning.objects.create(
                    order_item=item,
                    admin=admin,
                    amount=item.commission_amount,
                    status='pending'
                )
    
    @classmethod
    def create_supplier_payouts(cls, order):
        """Create payout records for suppliers"""
        from orders.models import SupplierPayout
        
        for item in order.items.filter(is_supplier_product=True):
            # Check if payout already exists
            if not hasattr(item, 'supplier_payout'):
                try:
                    SupplierPayout.objects.create(
                        supplier=item.product.owner,
                        order_item=item,
                        amount=item.supplier_payout_amount,
                        status='pending'
                    )
                except TypeError as e:
                    # If the model doesn't accept order_item, try alternative
                    print(f"Error creating payout: {e}")
                    # Alternative creation method
                    SupplierPayout.objects.create(
                        supplier=item.product.owner,
                        amount=item.supplier_payout_amount,
                        status='pending'
                    )
    
    @classmethod
    def send_order_confirmation(cls, order):
        """Send order confirmation email with receipt"""
        subject = f'Order Confirmation - {order.order_number}'
        
        # Get the full URL for the order detail
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        context = {
            'order': order,
            'customer': order.customer,
            'items': order.items.all(),
            'grand_total': order.grand_total,
            'subtotal_base': order.subtotal_base,
            'total_vat': order.total_vat,
            'site_name': 'HerosTechnology',
            'site_url': site_url,
        }
        
        try:
            html_message = render_to_string('orders/emails/order_confirmation.html', context)
            plain_message = f"Thank you for your order!\n\nOrder Number: {order.order_number}\nTotal: {order.grand_total} FRW\n\nView your order: {site_url}/orders/order/{order.id}/"
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.customer.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            # Log error but don't break the checkout flow
            print(f"Failed to send confirmation email: {e}")
    
    @classmethod
    def process_refund(cls, order, amount=None):
        """Process refund for an order"""
        from notifications.utils.notification_service import NotificationService
        
        if not amount:
            amount = order.grand_total
        
        # Create refund transaction
        transaction_id = f"REF-{secrets.token_hex(8).upper()}"
        
        transaction = PaymentTransaction.objects.create(
            order=order,
            transaction_id=transaction_id,
            amount=amount,
            payment_method=order.payment_method,
            status='success',
            provider=order.payment_method,
            response_data={'refunded_at': timezone.now().isoformat()}
        )
        
        order.payment_status = 'refunded'
        order.order_status = 'refunded'
        order.save()
        
        # Restore stock
        for item in order.items.all():
            item.product.increase_stock(item.quantity)
            item.status = 'refunded'
            item.save()
        
        # Notify customer about refund
        NotificationService.create_notification(
            user=order.customer,
            title=f"Order Refunded - {order.order_number}",
            message=f"Your order #{order.order_number} has been refunded. Amount: {amount:,.0f} FRW",
            notification_type='payment',
            priority='high',
            link=f'/orders/order/{order.id}/'
        )
        
        return True, transaction


class RealPaymentProcessor:
    """Placeholder for real payment gateway integration (for production)"""
    
    @classmethod
    def process_mobile_money(cls, order, phone_number, provider='mtn'):
        """
        Process real mobile money payment
        To be implemented when deploying to production
        """
        # This is a placeholder - you'll integrate actual API here
        # Example for MTN MoMo API, Airtel Money, etc.
        raise NotImplementedError("Real payment integration not implemented in development mode")