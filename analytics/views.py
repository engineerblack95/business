from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.decorators import role_required
from .utils.analytics_engine import AnalyticsEngine
from .models import DailySalesReport, PageView, SearchAnalytics
from orders.models import Order, OrderItem
from products.models import Product, ProductReview
from accounts.models import User


@login_required
@role_required(['admin'])
def analytics_dashboard_view(request):
    """Main analytics dashboard"""
    
    # Get date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Sales overview
    total_revenue = Order.objects.filter(
        created_at__gte=start_date,
        payment_status__in=['simulated', 'paid']
    ).aggregate(total=Sum('grand_total'))['total'] or 0
    
    total_orders = Order.objects.filter(
        created_at__gte=start_date,
        payment_status__in=['simulated', 'paid']
    ).count()
    
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    
    # Products stats
    total_products = Product.objects.count()
    products_sold = OrderItem.objects.filter(
        order__created_at__gte=start_date,
        order__payment_status__in=['simulated', 'paid']
    ).values('product').distinct().count()
    
    # Customer stats
    new_customers = User.objects.filter(
        date_joined__gte=start_date,
        role='customer'
    ).count()
    
    total_customers = User.objects.filter(role='customer').count()
    
    # Reviews
    total_reviews = ProductReview.objects.filter(created_at__gte=start_date).count()
    avg_rating = ProductReview.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    
    # Commission
    total_commission = OrderItem.objects.filter(
        order__created_at__gte=start_date,
        is_supplier_product=True,
        order__payment_status__in=['simulated', 'paid']
    ).aggregate(total=Sum('commission_amount'))['total'] or 0
    
    # Conversion rate
    conversion_data = AnalyticsEngine.get_conversion_rate(days)
    
    # Top products
    top_products = AnalyticsEngine.get_top_products(days=days)
    
    # Top suppliers
    top_suppliers = AnalyticsEngine.get_top_suppliers(days=days)
    
    # Popular searches
    popular_searches = AnalyticsEngine.get_popular_searches(days=7)
    
    # Daily sales for chart
    daily_reports = DailySalesReport.objects.filter(
        report_date__gte=start_date
    ).order_by('report_date')
    
    daily_data = {
        'dates': [r.report_date.strftime('%Y-%m-%d') for r in daily_reports],
        'revenue': [float(r.total_revenue) for r in daily_reports],
        'orders': [r.total_orders for r in daily_reports],
    }
    
    context = {
        'days': days,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'total_products': total_products,
        'products_sold': products_sold,
        'new_customers': new_customers,
        'total_customers': total_customers,
        'total_reviews': total_reviews,
        'avg_rating': avg_rating,
        'total_commission': total_commission,
        'conversion_rate': conversion_data['conversion_rate'],
        'unique_sessions': conversion_data['unique_sessions'],
        'top_products': top_products,
        'top_suppliers': top_suppliers,
        'popular_searches': popular_searches,
        'daily_data': daily_data,
    }
    
    return render(request, 'analytics/dashboard.html', context)


@login_required
@role_required(['admin'])
def sales_report_view(request):
    """Detailed sales report"""
    
    # Get date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from and date_to:
        from datetime import datetime
        start_date = datetime.strptime(date_from, '%Y-%m-%d')
        end_date = datetime.strptime(date_to, '%Y-%m-%d')
    else:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
    
    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        payment_status__in=['simulated', 'paid']
    )
    
    # Daily breakdown
    daily_breakdown = []
    current = start_date
    while current <= end_date:
        day_orders = orders.filter(created_at__date=current)
        daily_breakdown.append({
            'date': current,
            'orders': day_orders.count(),
            'revenue': day_orders.aggregate(total=Sum('grand_total'))['total'] or 0,
        })
        current += timedelta(days=1)
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_orders': orders.count(),
        'total_revenue': orders.aggregate(total=Sum('grand_total'))['total'] or 0,
        'daily_breakdown': daily_breakdown,
    }
    
    return render(request, 'analytics/sales_report.html', context)


@login_required
@role_required(['admin'])
def product_performance_view(request):
    """Product performance analytics"""
    
    products = Product.objects.annotate(
        total_sold=Sum('order_items__quantity'),
        total_revenue=Sum('order_items__final_price'),
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-total_sold')
    
    context = {
        'products': products[:50],
    }
    return render(request, 'analytics/product_performance.html', context)