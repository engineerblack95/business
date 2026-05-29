from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', views.analytics_dashboard_view, name='dashboard'),
    path('sales/', views.sales_report_view, name='sales_report'),
    path('products/', views.product_performance_view, name='product_performance'),
]