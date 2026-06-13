from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # ============================================================
    # CART URLs
    # ============================================================
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<uuid:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<uuid:item_id>/', views.update_cart_item, name='update_cart'),
    path('cart/remove/<uuid:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/count/', views.cart_count_view, name='cart_count'),
    
    # ============================================================
    # CHECKOUT & PAYMENT URLs
    # ============================================================
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment/<uuid:order_id>/', views.payment_view, name='payment'),
    path('confirmation/<uuid:order_id>/', views.order_confirmation_view, name='order_confirmation'),
    
    # ============================================================
    # ORDER URLs (Customer)
    # ============================================================
    path('my-orders/', views.order_list_view, name='order_list'),
    path('order/<uuid:order_id>/', views.order_detail_view, name='order_detail'),
    path('order/<uuid:order_id>/receipt/', views.download_receipt_view, name='download_receipt'),
    
    # ============================================================
    # ADMIN ORDER MANAGEMENT URLs
    # ============================================================
    path('admin/orders/', views.admin_orders_view, name='admin_orders'),
    path('admin/order/<uuid:order_id>/status/', views.update_order_status_view, name='update_order_status'),
    path('admin/order/<uuid:order_id>/cancel/', views.cancel_order_view, name='cancel_order'),
    
    # ============================================================
    # SUPPLIER ORDER URLs
    # ============================================================
    path('supplier/orders/', views.supplier_orders_view, name='supplier_orders'),
    
    # ============================================================
    # COMMISSION URLs (Legacy - Keep for backward compatibility)
    # ============================================================
    path('admin/commission/', views.commission_dashboard_view, name='commission_dashboard'),
    path('admin/commission/withdraw/', views.request_withdrawal_view, name='request_withdrawal'),
    
    # ============================================================
    # WALLET URLs (NEW - Auto-split payment system)
    # ============================================================
    # Supplier Wallet
    path('wallet/supplier/', views.supplier_wallet_view, name='supplier_wallet'),
    
    # Admin Wallet
    path('wallet/admin/', views.admin_wallet_view, name='admin_wallet'),
    
    # Withdrawal Requests (Unified)
    path('wallet/withdraw/request/', views.request_wallet_withdrawal_view, name='request_wallet_withdrawal'),
    
    # Process Withdrawal (Admin only)
    path('wallet/withdraw/process/<uuid:withdrawal_id>/', views.process_withdrawal_request_view, name='process_withdrawal'),
]