from decimal import Decimal
from django.utils import timezone
from ..models import PaymentTransaction, PaymentMethod
from ..utils.mobile_money import MTNMobileMoney, AirtelMoney
from orders.models import Order
from dashboard.utils.notifications import NotificationManager

class PaymentGateway:
    """Main payment gateway interface"""
    
    @classmethod
    def get_payment_processor(cls, payment_method, provider):
        """Get appropriate payment processor"""
        
        if payment_method.startswith('mobile_money'):
            if provider == 'mtn':
                return MTNMobileMoney()
            elif provider == 'airtel':
                return AirtelMoney()
        
        # Simulated processor for development
        return None
    
    @classmethod
    def initiate_payment(cls, order, payment_method, **kwargs):
        """Initiate payment for an order"""
        
        # Create payment transaction record
        transaction = PaymentTransaction.objects.create(
            order=order,
            customer=order.customer,
            amount=order.grand_total,
            currency='RWF',
            payment_method=payment_method,
            status='initiated',
            subtotal=order.subtotal_base,
            vat_amount=order.total_vat,
            ip_address=kwargs.get('ip_address', ''),
            user_agent=kwargs.get('user_agent', '')
        )
        
        # Process based on payment method
        if payment_method == 'mobile_money_mtn':
            mobile_number = kwargs.get('mobile_money_number', '')
            transaction.mobile_money_number = mobile_number
            transaction.mobile_money_provider = 'mtn'
            transaction.save()
            
            processor = MTNMobileMoney()
            success, txn_id, message = processor.initiate_payment(
                phone_number=mobile_number,
                amount=float(order.grand_total),
                transaction_id=str(transaction.id)
            )
            
            if success:
                transaction.status = 'processing'
                transaction.provider_transaction_id = txn_id
                transaction.save()
                
                # In production, you would redirect to payment page
                return transaction, True, message
            else:
                transaction.mark_failed(message)
                return transaction, False, message
        
        elif payment_method == 'mobile_money_airtel':
            mobile_number = kwargs.get('mobile_money_number', '')
            transaction.mobile_money_number = mobile_number
            transaction.mobile_money_provider = 'airtel'
            transaction.save()
            
            processor = AirtelMoney()
            success, txn_id, message = processor.initiate_payment(
                phone_number=mobile_number,
                amount=float(order.grand_total),
                transaction_id=str(transaction.id)
            )
            
            if success:
                transaction.status = 'processing'
                transaction.provider_transaction_id = txn_id
                transaction.save()
                return transaction, True, message
            else:
                transaction.mark_failed(message)
                return transaction, False, message
        
        else:
            # Simulate payment for development
            return cls.simulate_payment(transaction, **kwargs)
    
    @classmethod
    def simulate_payment(cls, transaction, **kwargs):
        """Simulate payment for development/testing"""
        
        # Update transaction status
        transaction.status = 'processing'
        transaction.provider = 'simulated'
        transaction.save()
        
        # Simulate processing
        import time
        time.sleep(2)
        
        # Always succeed in simulation
        transaction.mark_completed(provider_txn_id=f"SIM-{transaction.transaction_id}")
        
        # Update order status
        order = transaction.order
        order.payment_status = 'paid'
        order.paid_at = timezone.now()
        order.save()
        
        # Process commissions
        from .commission_handler import CommissionHandler
        CommissionHandler.process_order_commissions(order, transaction)
        
        # Send confirmation
        from dashboard.utils.notifications import NotificationManager
        
        # Notify customer
        NotificationManager.create_notification(
            user=order.customer,
            title="Payment Successful",
            message=f"Your payment of {order.grand_total} FRW for order #{order.order_number} has been confirmed.",
            notification_type='payment',
            priority='high',
            link=f'/orders/order/{order.id}/'
        )
        
        return transaction, True, "Payment completed successfully"
    
    @classmethod
    def verify_payment(cls, transaction_id):
        """Verify payment status"""
        try:
            transaction = PaymentTransaction.objects.get(transaction_id=transaction_id)
            
            if transaction.provider == 'mtn':
                processor = MTNMobileMoney()
                status = processor.check_payment_status(transaction.provider_transaction_id)
                
                if status == 'SUCCESSFUL':
                    transaction.mark_completed()
                    return True, "Payment verified"
                elif status == 'FAILED':
                    transaction.mark_failed("Payment failed")
                    return False, "Payment failed"
            
            return False, "Unknown payment status"
            
        except PaymentTransaction.DoesNotExist:
            return False, "Transaction not found"
    
    @classmethod
    def refund_payment(cls, transaction, amount=None, reason=None):
        """Process refund for a payment"""
        
        if not amount:
            amount = transaction.amount
        
        if transaction.status != 'completed':
            return False, "Only completed transactions can be refunded"
        
        # Process refund based on provider
        if transaction.provider == 'simulated':
            transaction.mark_refunded(reason)
            
            # Update order
            order = transaction.order
            order.payment_status = 'refunded'
            order.order_status = 'refunded'
            order.save()
            
            return True, "Refund processed successfully"
        
        # For real providers, implement actual refund API call
        return False, "Refund not implemented for this provider"