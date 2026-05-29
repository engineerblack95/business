from decimal import Decimal
from django.db.models import Sum
from django.conf import settings
from orders.models import CommissionEarning, WithdrawalRequest

class CommissionCalculator:
    """Calculate and manage admin commissions"""
    
    COMMISSION_RATE = Decimal(str(getattr(settings, 'COMMISSION_RATE', 7))) / Decimal('100')
    
    @classmethod
    def calculate_commission(cls, base_price, quantity=1):
        """Calculate commission for a single item"""
        return (base_price * cls.COMMISSION_RATE * quantity).quantize(Decimal('0.01'))
    
    @classmethod
    def get_admin_commission_summary(cls, admin_user):
        """Get summary of admin's commission earnings"""
        
        # Total earned commission (all time)
        total_earned = CommissionEarning.objects.filter(
            admin=admin_user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Available commission (not withdrawn)
        available = CommissionEarning.objects.filter(
            admin=admin_user,
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Withdrawn commission
        withdrawn = CommissionEarning.objects.filter(
            admin=admin_user,
            status='withdrawn'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Pending withdrawal requests
        pending_requests = WithdrawalRequest.objects.filter(
            admin=admin_user,
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'total_earned': total_earned,
            'available': available,
            'withdrawn': withdrawn,
            'pending_requests': pending_requests,
        }
    
    @classmethod
    def get_available_commission(cls, admin_user):
        """Get available commission for withdrawal"""
        result = CommissionEarning.objects.filter(
            admin=admin_user,
            status='pending'
        ).aggregate(total=Sum('amount'))['total']
        return result or Decimal('0.00')
    
    @classmethod
    def mark_commission_as_withdrawn(cls, withdrawal_request):
        """Mark commissions as withdrawn when admin withdraws"""
        # This would need to track which commission earnings are included
        # For simplicity, we'll mark the most recent ones first
        commissions = CommissionEarning.objects.filter(
            admin=withdrawal_request.admin,
            status='pending'
        ).order_by('created_at')
        
        remaining = withdrawal_request.amount
        updated_commissions = []
        
        for commission in commissions:
            if remaining <= 0:
                break
            
            if commission.amount <= remaining:
                commission.status = 'withdrawn'
                commission.withdrawn_at = withdrawal_request.completed_at
                commission.withdrawal_reference = withdrawal_request.request_reference
                commission.save()
                remaining -= commission.amount
                updated_commissions.append(commission)
            else:
                # Split commission if partial withdrawal
                # For simplicity, we'll not split and leave as pending
                pass
        
        return updated_commissions


class SupplierPayoutCalculator:
    """Calculate supplier payouts after commission"""
    
    @classmethod
    def calculate_supplier_payout(cls, base_price, quantity=1):
        """Calculate supplier payout amount after commission"""
        from django.conf import settings
        commission_rate = Decimal(str(getattr(settings, 'COMMISSION_RATE', 7))) / Decimal('100')
        commission = (base_price * commission_rate * quantity).quantize(Decimal('0.01'))
        payout = (base_price * quantity - commission).quantize(Decimal('0.01'))
        return payout
    
    @classmethod
    def get_supplier_payout_summary(cls, supplier_user):
        """Get summary of supplier's pending payouts"""
        from orders.models import SupplierPayout
        
        total_pending = SupplierPayout.objects.filter(
            supplier=supplier_user,
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        total_paid = SupplierPayout.objects.filter(
            supplier=supplier_user,
            status='paid'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'pending': total_pending,
            'paid': total_paid,
            'total': total_pending + total_paid,
        }