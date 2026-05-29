from django.db import models  # <-- ADD THIS IMPORT
from django.db.models import Sum, Count, Q, Avg, F  # <-- ADD F here
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from orders.models import Order, OrderItem
from products.models import Product, ProductReview
from accounts.models import User


class DashboardAnalytics:
    """Analytics for dashboard"""
    
    @staticmethod
    def get_admin_analytics():
        """Get analytics for admin dashboard"""
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Revenue stats
        total_revenue = Order.objects.filter(
            payment_status__in=['simulated', 'paid']
        ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        revenue_today = Order.objects.filter(
            payment_status__in=['simulated', 'paid'],
            created_at__date=today
        ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        revenue_week = Order.objects.filter(
            payment_status__in=['simulated', 'paid'],
            created_at__date__gte=week_ago
        ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        revenue_month = Order.objects.filter(
            payment_status__in=['simulated', 'paid'],
            created_at__date__gte=month_ago
        ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        # Order stats
        total_orders = Order.objects.count()
        pending_orders = Order.objects.filter(order_status='pending').count()
        processing_orders = Order.objects.filter(order_status='processing').count()
        completed_orders = Order.objects.filter(order_status='delivered').count()
        cancelled_orders = Order.objects.filter(order_status='cancelled').count()
        
        # User stats
        total_customers = User.objects.filter(role='customer').count()
        total_suppliers = User.objects.filter(role='supplier', is_approved_supplier=True).count()
        pending_suppliers = User.objects.filter(role='supplier', is_approved_supplier=False).count()
        total_team_members = User.objects.filter(role='team_member').count()
        
        # Product stats
        total_products = Product.objects.count()
        pending_products = Product.objects.filter(status='pending_approval').count()
        approved_products = Product.objects.filter(status='approved').count()
        out_of_stock_products = Product.objects.filter(exact_quantity=0, status='approved').count()
        
        # FIXED: Use F() directly instead of models.F()
        low_stock_products = Product.objects.filter(
            exact_quantity__lte=F('low_stock_threshold'),
            exact_quantity__gt=0
        ).count()
        
        # Commission stats
        from orders.models import CommissionEarning
        total_commission = CommissionEarning.objects.filter(
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Recent activity
        recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:10]
        recent_products = Product.objects.select_related('owner').order_by('-created_at')[:10]
        
        # Daily sales for chart (last 7 days)
        daily_sales = []
        for i in range(7):
            day = today - timedelta(days=i)
            sales = Order.objects.filter(
                payment_status__in=['simulated', 'paid'],
                created_at__date=day
            ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
            daily_sales.append({
                'date': day.strftime('%Y-%m-%d'),
                'sales': float(sales)
            })
        
        return {
            'revenue': {
                'total': float(total_revenue),
                'today': float(revenue_today),
                'week': float(revenue_week),
                'month': float(revenue_month),
            },
            'orders': {
                'total': total_orders,
                'pending': pending_orders,
                'processing': processing_orders,
                'completed': completed_orders,
                'cancelled': cancelled_orders,
            },
            'users': {
                'customers': total_customers,
                'suppliers': total_suppliers,
                'pending_suppliers': pending_suppliers,
                'team_members': total_team_members,
            },
            'products': {
                'total': total_products,
                'pending': pending_products,
                'approved': approved_products,
                'out_of_stock': out_of_stock_products,
                'low_stock': low_stock_products,
            },
            'commission': {
                'total_available': float(total_commission),
            },
            'recent_orders': recent_orders,
            'recent_products': recent_products,
            'daily_sales': daily_sales,
        }
    
    @staticmethod
    def get_supplier_analytics(supplier):
        """Get analytics for supplier dashboard"""
        
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)
        
        # Products
        products = Product.objects.filter(owner=supplier)
        total_products = products.count()
        approved_products = products.filter(status='approved').count()
        pending_products = products.filter(status='pending_approval').count()
        out_of_stock = products.filter(exact_quantity=0).count()
        
        # FIXED: Use F() directly
        low_stock = products.filter(
            exact_quantity__lte=F('low_stock_threshold'),
            exact_quantity__gt=0
        ).count()
        
        # Sales
        order_items = OrderItem.objects.filter(
            product__owner=supplier,
            is_supplier_product=True,
            order__payment_status__in=['simulated', 'paid']
        )
        
        total_sales = order_items.aggregate(total=Sum('final_price'))['total'] or Decimal('0.00')
        total_units_sold = order_items.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Sales this month
        monthly_sales = order_items.filter(
            order__created_at__date__gte=month_ago
        ).aggregate(total=Sum('final_price'))['total'] or Decimal('0.00')
        
        # Commission and payouts
        total_commission_deducted = order_items.aggregate(total=Sum('commission_amount'))['total'] or Decimal('0.00')
        
        # FIXED: Use SupplierPayoutHistory from suppliers.models (not orders.models)
        try:
            from suppliers.models import SupplierPayoutHistory
            pending_payouts = SupplierPayoutHistory.objects.filter(
                supplier=supplier,
                status='pending'
            ).aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
            
            paid_payouts = SupplierPayoutHistory.objects.filter(
                supplier=supplier,
                status='completed'
            ).aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
        except ImportError:
            # Fallback if SupplierPayoutHistory doesn't exist
            pending_payouts = Decimal('0.00')
            paid_payouts = Decimal('0.00')
        
        # Recent orders
        recent_orders = Order.objects.filter(
            items__product__owner=supplier
        ).distinct().order_by('-created_at')[:10]
        
        # Top selling products
        top_products = products.annotate(
            total_sold=Sum('order_items__quantity')
        ).order_by('-total_sold')[:5]
        
        # Product ratings
        avg_rating = ProductReview.objects.filter(
            product__owner=supplier
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        
        return {
            'products': {
                'total': total_products,
                'approved': approved_products,
                'pending': pending_products,
                'out_of_stock': out_of_stock,
                'low_stock': low_stock,
            },
            'sales': {
                'total': float(total_sales),
                'monthly': float(monthly_sales),
                'units_sold': total_units_sold,
            },
            'commission': {
                'total_deducted': float(total_commission_deducted),
            },
            'payouts': {
                'pending': float(pending_payouts),
                'paid': float(paid_payouts),
            },
            'avg_rating': round(avg_rating, 2),
            'recent_orders': recent_orders,
            'top_products': top_products,
        }
    
    @staticmethod
    def get_customer_analytics(customer):
        """Get analytics for customer dashboard"""
        
        # Order stats
        orders = Order.objects.filter(customer=customer)
        total_orders = orders.count()
        total_spent = orders.filter(
            payment_status__in=['simulated', 'paid']
        ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        
        pending_orders = orders.filter(order_status='pending').count()
        processing_orders = orders.filter(order_status='processing').count()
        delivered_orders = orders.filter(order_status='delivered').count()
        
        # Recent orders
        recent_orders = orders.order_by('-created_at')[:10]
        
        # Wishlist
        from products.models import Wishlist
        wishlist_count = Wishlist.objects.filter(customer=customer).count()
        
        # Reviews
        review_count = ProductReview.objects.filter(customer=customer).count()
        
        # Order items
        total_items_purchased = OrderItem.objects.filter(
            order__customer=customer,
            order__payment_status__in=['simulated', 'paid']
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        return {
            'orders': {
                'total': total_orders,
                'pending': pending_orders,
                'processing': processing_orders,
                'delivered': delivered_orders,
                'total_spent': float(total_spent),
                'total_items': total_items_purchased,
            },
            'wishlist_count': wishlist_count,
            'review_count': review_count,
            'recent_orders': recent_orders,
        }