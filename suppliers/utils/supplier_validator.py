from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Avg  # <-- ADD THIS IMPORT


class SupplierPerformanceCalculator:
    """Calculate supplier performance metrics"""
    
    @staticmethod
    def calculate_performance_score(supplier):
        """Calculate overall performance score (0-100)"""
        from orders.models import OrderItem
        from products.models import ProductReview
        
        # Sales volume (40%)
        order_items = OrderItem.objects.filter(
            product__owner=supplier,
            order__payment_status__in=['simulated', 'paid']
        )
        total_sales = order_items.aggregate(total=Sum('final_price'))['total'] or Decimal('0.00')
        sales_score = min(40, (float(total_sales) / 1000000) * 10)  # 1M FRW = 10 points
        
        # Rating (30%)
        reviews = ProductReview.objects.filter(product__owner=supplier)
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        rating_score = (avg_rating / 5) * 30
        
        # Response rate (15%)
        # This would need to track customer inquiries
        response_score = 15  # Default placeholder
        
        # Product quality (15%)
        # Based on return rate, quality reports
        quality_score = 15  # Default placeholder
        
        total_score = sales_score + rating_score + response_score + quality_score
        
        return round(total_score, 2)
    
    @staticmethod
    def get_supplier_tier(score):
        """Determine supplier tier based on performance score"""
        if score >= 90:
            return {'tier': 'Platinum', 'commission_rate': 5, 'badge': '💎 Platinum'}
        elif score >= 75:
            return {'tier': 'Gold', 'commission_rate': 6, 'badge': '🥇 Gold'}
        elif score >= 60:
            return {'tier': 'Silver', 'commission_rate': 7, 'badge': '🥈 Silver'}
        elif score >= 40:
            return {'tier': 'Bronze', 'commission_rate': 8, 'badge': '🥉 Bronze'}
        else:
            return {'tier': 'Standard', 'commission_rate': 10, 'badge': '⭐ Standard'}
    
    @staticmethod
    def get_weekly_report(supplier):
        """Generate weekly performance report"""
        week_ago = timezone.now() - timedelta(days=7)
        
        from orders.models import OrderItem
        weekly_items = OrderItem.objects.filter(
            product__owner=supplier,
            order__created_at__gte=week_ago,
            order__payment_status__in=['simulated', 'paid']
        )
        
        total_sales = weekly_items.aggregate(total=Sum('final_price'))['total'] or Decimal('0.00')
        units_sold = weekly_items.aggregate(total=Sum('quantity'))['total'] or 0
        orders_count = weekly_items.values('order').distinct().count()
        avg_order_value = total_sales / orders_count if orders_count > 0 else Decimal('0.00')
        
        return {
            'total_sales': total_sales,
            'units_sold': units_sold,
            'orders_count': orders_count,
            'avg_order_value': avg_order_value
        }