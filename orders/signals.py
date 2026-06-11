from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import OrderItem, CommissionEarning, SupplierPayout
from accounts.models import User


@receiver(post_save, sender=OrderItem)
def create_commission_records(sender, instance, created, **kwargs):
    """
    Auto-create CommissionEarning and SupplierPayout when OrderItem is saved
    This is CRITICAL for the commission system to work
    """
    
    if created and instance.is_supplier_product and instance.commission_amount > 0:
        # Get the admin user (superuser or first admin)
        admin_user = User.objects.filter(role='admin').first()
        
        if admin_user:
            # Create CommissionEarning for admin
            commission_earning, created = CommissionEarning.objects.get_or_create(
                order_item=instance,
                defaults={
                    'admin': admin_user,
                    'amount': instance.commission_amount,
                    'status': 'pending'
                }
            )
            
            # Create SupplierPayout record
            supplier_payout, created = SupplierPayout.objects.get_or_create(
                order_item=instance,
                defaults={
                    'supplier': instance.product.owner,
                    'amount': instance.supplier_payout_amount,
                    'commission_deducted': instance.commission_amount,
                    'status': 'pending'
                }
            )
            
            # Optional: Print debug info
            print(f"✅ Commission created: {instance.commission_amount} FRW for order {instance.order.order_number}")


@receiver(post_save, sender=OrderItem)
def update_supplier_metrics(sender, instance, created, **kwargs):
    """Update supplier's performance metrics when order item is created"""
    
    if created and instance.is_supplier_product:
        try:
            supplier = instance.product.owner
            
            # Update supplier profile metrics if exists
            if hasattr(supplier, 'supplier_profile'):
                profile = supplier.supplier_profile
                profile.total_sales += instance.supplier_payout_amount
                profile.total_products_sold += instance.quantity
                profile.save()
                print(f"✅ Updated metrics for supplier: {supplier.email}")
        except Exception as e:
            print(f"Error updating supplier metrics: {e}")