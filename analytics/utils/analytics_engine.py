from django.db.models import Sum, Count, Q, Avg, Min  # <-- ADD Min import
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from orders.models import Order, OrderItem
from products.models import Product, ProductReview
from accounts.models import User
from ..models import DailySalesReport, PageView, ConversionTracking, SearchAnalytics

class AnalyticsEngine:
    """Generate analytics reports"""
    
    @staticmethod
    def generate_daily_report(date=None):
        """Generate daily sales report"""
        if not date:
            date = timezone.now().date()
        
        # Get orders for the day
        orders = Order.objects.filter(
            created_at__date=date,
            payment_status__in=['simulated', 'paid']
        )
        
        total_orders = orders.count()
        total_revenue = orders.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        # Total items sold
        order_items = OrderItem.objects.filter(
            order__created_at__date=date,
            order__payment_status__in=['simulated', 'paid']
        )
        total_items_sold = order_items.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Average order value
        avg_order_value = total_revenue / total_orders if total_orders > 0 else Decimal('0.00')
        
        # New vs returning customers
        new_customers = User.objects.filter(
            date_joined__date=date,
            role='customer'
        ).count()
        
        returning_customers = orders.values('customer').distinct().count() - new_customers
        
        # New products
        new_products = Product.objects.filter(created_at__date=date).count()
        
        # Products sold
        products_sold = order_items.values('product').distinct().count()
        
        # Total commission
        total_commission = order_items.aggregate(total=Sum('commission_amount'))['total'] or Decimal('0.00')
        
        # Create or update report
        report, created = DailySalesReport.objects.update_or_create(
            report_date=date,
            defaults={
                'total_orders': total_orders,
                'total_revenue': total_revenue,
                'total_items_sold': total_items_sold,
                'average_order_value': avg_order_value,
                'new_customers': new_customers,
                'returning_customers': returning_customers,
                'new_products': new_products,
                'products_sold': products_sold,
                'total_commission': total_commission,
            }
        )
        
        return report
    
    @staticmethod
    def get_conversion_rate(days=30):
        """Calculate conversion rate for the period"""
        start_date = timezone.now() - timedelta(days=days)
        
        # Get unique sessions
        unique_sessions = PageView.objects.filter(
            created_at__gte=start_date
        ).values('session_key').distinct().count()
        
        # Get completed purchases
        purchases = Order.objects.filter(
            created_at__gte=start_date,
            payment_status__in=['simulated', 'paid']
        ).count()  # Fixed: use count() instead of values('id').count()
        
        conversion_rate = (purchases / unique_sessions * 100) if unique_sessions > 0 else 0
        
        return {
            'unique_sessions': unique_sessions,
            'purchases': purchases,
            'conversion_rate': round(conversion_rate, 2)
        }
    
    @staticmethod
    def get_top_products(limit=10, days=30):
        """Get top selling products"""
        start_date = timezone.now() - timedelta(days=days)
        
        top_products = Product.objects.filter(
            order_items__order__created_at__gte=start_date,
            order_items__order__payment_status__in=['simulated', 'paid']
        ).annotate(
            total_sold=Sum('order_items__quantity'),
            total_revenue=Sum('order_items__final_price')
        ).order_by('-total_sold')[:limit]
        
        return top_products
    
    @staticmethod
    def get_top_suppliers(limit=10, days=30):
        """Get top performing suppliers"""
        start_date = timezone.now() - timedelta(days=days)
        
        top_suppliers = User.objects.filter(
            role='supplier',
            products__order_items__order__created_at__gte=start_date,
            products__order_items__order__payment_status__in=['simulated', 'paid']
        ).annotate(
            total_sales=Sum('products__order_items__final_price'),
            total_units=Sum('products__order_items__quantity'),
            avg_rating=Avg('products__reviews__rating')
        ).order_by('-total_sales')[:limit]
        
        return top_suppliers
    
    @staticmethod
    def get_popular_searches(limit=10, days=7):
        """Get most searched terms"""
        start_date = timezone.now() - timedelta(days=days)
        
        popular = SearchAnalytics.objects.filter(
            created_at__gte=start_date
        ).values('search_term').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]
        
        return popular
    
    @staticmethod
    def get_customer_retention_rate():
        """Calculate customer retention rate"""
        # Customers who made first purchase in last 30 days
        first_purchases = Order.objects.filter(
            payment_status__in=['simulated', 'paid']
        ).values('customer').annotate(
            first_purchase=Min('created_at')
        ).filter(first_purchase__gte=timezone.now() - timedelta(days=30))
        
        total_new_customers = first_purchases.count()
        
        # Who made second purchase within 30 days
        retained = 0
        for data in first_purchases:
            customer = data['customer']
            second_purchase = Order.objects.filter(
                customer_id=customer,
                created_at__gt=data['first_purchase'],
                created_at__lte=data['first_purchase'] + timedelta(days=30),
                payment_status__in=['simulated', 'paid']
            ).exists()
            if second_purchase:
                retained += 1
        
        retention_rate = (retained / total_new_customers * 100) if total_new_customers > 0 else 0
        
        return round(retention_rate, 2)
    
    @staticmethod
    def track_conversion(session_key, stage, user=None, product=None, value=0):
        """Track conversion funnel step"""
        ConversionTracking.objects.create(
            session_key=session_key,
            user=user,
            stage=stage,
            product=product,
            value=value
        )