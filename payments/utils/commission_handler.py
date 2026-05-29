from decimal import Decimal
from django.db import transaction as db_transaction
from django.conf import settings
from ..models import CommissionRecord, SupplierPayout, WithdrawalRequest
from orders.models import OrderItem

class CommissionHandler:
    """Handle commission calculations and distributions"""
    
    COMMISSION_RATE = Decimal(str(getattr(settings, 'COMMISSION_RATE', 7))) / Decimal('100')
    
    @classmethod
    def calculate_commission(cls, base_price, quantity=1):
        """Calculate commission for a single item"""
        return (base_price * cls.COMMISSION_RATE * quantity).quantize(Decimal('0.01'))
    
    @classmethod
    @db_transaction.atomic
    def process_order_commissions(cls, order, transaction):
        """Process all commissions for an order"""
        
        from accounts.models import User
        
        # Get admin (first admin user)
        admin = User.objects.filter(role='admin').first()
        
        if not admin:
            return
        
        commissions_created = []
        
        for item in order.items.filter(is_supplier_product=True):
            # Calculate commission
            commission_amount = cls.calculate_commission(item.base_price, item.quantity)
            
            # Create commission record
            commission = CommissionRecord.objects.create(
                order_item=item,
                transaction=transaction,
                commission_type='product_sale',
                amount=commission_amount,
                rate=float(cls.COMMISSION_RATE * 100),
                admin=admin,
                is_withdrawn=False
            )
            
            commissions_created.append(commission)
            
            # Update order item with commission amount
            item.commission_amount = commission_amount
            item.supplier_payout_amount = item.base_price * item.quantity - commission_amount
            item.save()
        
        return commissions_created
    
    @classmethod
    def get_admin_commission_summary(cls, admin_user):
        """Get summary of admin's commission earnings"""
        
        total_earned = CommissionRecord.objects.filter(
            admin=admin_user
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        available = CommissionRecord.objects.filter(
            admin=admin_user,
            is_withdrawn=False
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        withdrawn = CommissionRecord.objects.filter(
            admin=admin_user,
            is_withdrawn=True
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        # Pending withdrawal requests
        pending_requests = WithdrawalRequest.objects.filter(
            admin=admin_user,
            status='pending'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'total_earned': total_earned,
            'available': available,
            'withdrawn': withdrawn,
            'pending_requests': pending_requests,
        }
    
    @classmethod
    @db_transaction.atomic
    def process_withdrawal(cls, withdrawal_request):
        """Process commission withdrawal"""
        
        # Get available commissions
        commissions = CommissionRecord.objects.filter(
            admin=withdrawal_request.admin,
            is_withdrawn=False
        ).order_by('created_at')
        
        remaining = withdrawal_request.amount
        commissions_to_withdraw = []
        
        for commission in commissions:
            if remaining <= 0:
                break
            
            if commission.amount <= remaining:
                commission.is_withdrawn = True
                commission.withdrawn_at = withdrawal_request.completed_at
                commission.withdrawal_reference = withdrawal_request.request_code
                commission.save()
                remaining -= commission.amount
                commissions_to_withdraw.append(commission)
            else:
                # For partial commission withdrawal, we would need to split
                # For simplicity, we'll leave it for next withdrawal
                pass
        
        return commissions_to_withdraw


class SupplierPayoutHandler:
    """Handle supplier payouts"""
    
    @classmethod
    def get_supplier_pending_payouts(cls, supplier):
        """Get pending payouts for supplier"""
        from orders.models import OrderItem
        
        pending_items = OrderItem.objects.filter(
            product__owner=supplier,
            is_supplier_product=True,
            supplier_payout__isnull=True,
            order__payment_status__in=['simulated', 'paid']
        )
        
        total_pending = pending_items.aggregate(
            total=models.Sum('supplier_payout_amount')
        )['total'] or Decimal('0.00')
        
        return {
            'items': pending_items,
            'total': total_pending,
            'count': pending_items.count()
        }
    
    @classmethod
    @db_transaction.atomic
    def create_payout(cls, supplier, period_start, period_end):
        """Create payout for supplier for a period"""
        
        # Get unpaid order items for period
        order_items = OrderItem.objects.filter(
            product__owner=supplier,
            is_supplier_product=True,
            supplier_payout__isnull=True,
            order__payment_status__in=['simulated', 'paid'],
            order__paid_at__date__gte=period_start,
            order__paid_at__date__lte=period_end
        )
        
        if not order_items.exists():
            return None
        
        total_amount = order_items.aggregate(
            total=models.Sum('supplier_payout_amount')
        )['total'] or Decimal('0.00')
        
        total_commission = order_items.aggregate(
            total=models.Sum('commission_amount')
        )['total'] or Decimal('0.00')
        
        # Create payout
        payout = SupplierPayout.objects.create(
            supplier=supplier,
            amount=total_amount + total_commission,
            commission_deducted=total_commission,
            net_amount=total_amount,
            period_start=period_start,
            period_end=period_end,
            payout_method='mobile_money',
            status='pending'
        )
        
        # Link order items
        payout.order_items.set(order_items)
        
        return payout