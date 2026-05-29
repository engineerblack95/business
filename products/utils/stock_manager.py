from django.core.cache import cache
from django.db import transaction
from decimal import Decimal
from products.models import StockMovement  # Add this import
from django.db.models import F

class StockManager:
    """Manage product stock operations"""
    
    @staticmethod
    def check_stock(product, requested_quantity):
        """Check if requested quantity is available"""
        return product.exact_quantity >= requested_quantity
    
    @staticmethod
    @transaction.atomic
    def reserve_stock(product, quantity, order_item):
        """Reserve stock for an order"""
        if product.exact_quantity >= quantity:
            product.exact_quantity -= quantity
            product.save()
            
            # Log stock movement
            StockMovement.objects.create(
                product=product,
                order_item=order_item,
                quantity=-quantity,
                movement_type='sale',
                notes=f"Reserved for order {order_item.order.id}"
            )
            return True
        return False
    
    @staticmethod
    @transaction.atomic
    def release_stock(product, quantity, order_item, reason):
        """Release reserved stock (order cancelled/returned)"""
        product.exact_quantity += quantity
        product.save()
        
        StockMovement.objects.create(
            product=product,
            order_item=order_item,
            quantity=quantity,
            movement_type='release',
            notes=f"Released due to: {reason}"
        )
    
    @staticmethod
    def get_low_stock_products():
        """Get all products with low stock"""
        from products.models import Product
        return Product.objects.filter(
            exact_quantity__lte=F('low_stock_threshold'),
            exact_quantity__gt=0,
            status='approved'
        )
    
    @staticmethod
    def get_out_of_stock_products():
        """Get all out of stock products"""
        from products.models import Product
        return Product.objects.filter(
            exact_quantity=0,
            status='approved'
        )