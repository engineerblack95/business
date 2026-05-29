from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<uuid:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<uuid:item_id>/', views.update_cart_item, name='update_cart'),
    path('cart/remove/<uuid:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    
    # Checkout & Payment
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment/<uuid:order_id>/', views.payment_view, name='payment'),
    path('confirmation/<uuid:order_id>/', views.order_confirmation_view, name='order_confirmation'),
    
    # Orders
    path('my-orders/', views.order_list_view, name='order_list'),
    path('order/<uuid:order_id>/', views.order_detail_view, name='order_detail'),
    path('order/<uuid:order_id>/receipt/', views.download_receipt_view, name='download_receipt'),
    
    # Admin
    path('admin/orders/', views.admin_orders_view, name='admin_orders'),
    path('admin/order/<uuid:order_id>/status/', views.update_order_status_view, name='update_order_status'),
    path('admin/order/<uuid:order_id>/cancel/', views.cancel_order_view, name='cancel_order'),
    
    # Supplier
    path('supplier/orders/', views.supplier_orders_view, name='supplier_orders'),
    
    # Commission
    path('admin/commission/', views.commission_dashboard_view, name='commission_dashboard'),
    path('admin/commission/withdraw/', views.request_withdrawal_view, name='request_withdrawal'),
]