from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class DailySalesReport(models.Model):
    """Daily sales analytics"""
    
    report_date = models.DateField(unique=True)
    
    # Sales metrics
    total_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_items_sold = models.IntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Customer metrics
    new_customers = models.IntegerField(default=0)
    returning_customers = models.IntegerField(default=0)
    
    # Product metrics
    new_products = models.IntegerField(default=0)
    products_sold = models.IntegerField(default=0)
    
    # Commission metrics
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-report_date']
    
    def __str__(self):
        return f"Report for {self.report_date}"


class PageView(models.Model):
    """Track page views for analytics"""
    
    PAGE_TYPES = [
        ('home', 'Homepage'),
        ('product', 'Product Page'),
        ('category', 'Category Page'),
        ('cart', 'Cart Page'),
        ('checkout', 'Checkout Page'),
        ('dashboard', 'Dashboard'),
        ('profile', 'Profile Page'),
        ('search', 'Search Results'),
        ('other', 'Other'),
    ]
    
    page_type = models.CharField(max_length=20, choices=PAGE_TYPES)
    page_url = models.CharField(max_length=500)
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40, db_index=True)
    
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    referer = models.URLField(blank=True, null=True)
    
    # Time spent on page (seconds)
    time_spent = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['page_type', '-created_at']),
            models.Index(fields=['session_key']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.page_type} - {self.created_at}"


class ConversionTracking(models.Model):
    """Track conversion funnels"""
    
    CONVERSION_STAGES = [
        ('visit', 'Visit'),
        ('view_product', 'Product View'),
        ('add_to_cart', 'Add to Cart'),
        ('initiate_checkout', 'Initiate Checkout'),
        ('purchase', 'Purchase'),
    ]
    
    session_key = models.CharField(max_length=40, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    stage = models.CharField(max_length=20, choices=CONVERSION_STAGES)
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['session_key', 'stage']),
            models.Index(fields=['created_at']),
        ]


class SearchAnalytics(models.Model):
    """Track search queries"""
    
    search_term = models.CharField(max_length=255)
    results_count = models.IntegerField(default=0)
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40)
    
    ip_address = models.GenericIPAddressField()
    
    # Did user click any result?
    clicked_result = models.BooleanField(default=False)
    clicked_product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Search Analytics"
        indexes = [
            models.Index(fields=['search_term']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Search: '{self.search_term}' - {self.results_count} results"