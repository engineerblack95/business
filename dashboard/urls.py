from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # ============================================================
    # REDIRECT & ROLE-BASED DASHBOARDS
    # ============================================================
    path('', views.dashboard_redirect_view, name='home'),
    
    # Role-based dashboards
    path('admin/', views.admin_dashboard_view, name='admin'),
    path('supplier/', views.supplier_dashboard_view, name='supplier'),
    path('customer/', views.customer_dashboard_view, name='customer'),
    path('team/', views.team_dashboard_view, name='team'),
    
    # ============================================================
    # TEAM MANAGEMENT (Admin only)
    # ============================================================
    path('admin/team/', views.manage_team_members_view, name='manage_team'),
    path('admin/team/edit/<uuid:user_id>/', views.edit_team_member_view, name='edit_team_member'),
    path('admin/team/remove/<uuid:user_id>/', views.remove_team_member_view, name='remove_team_member'),
    
    # ============================================================
    # SUPPLIER MANAGEMENT (Admin only)
    # ============================================================
    path('admin/suppliers/', views.manage_suppliers_view, name='manage_suppliers'),
    path('admin/suppliers/approve/<uuid:user_id>/', views.approve_supplier_view, name='approve_supplier'),
    path('admin/suppliers/reject/<uuid:user_id>/', views.reject_supplier_view, name='reject_supplier'),
    
    # ============================================================
    # PRODUCT MANAGEMENT
    # ============================================================
    path('admin/products/', views.manage_products_dashboard, name='manage_products'),
    path('quick-stock-update/', views.quick_stock_update_view, name='quick_stock_update'),
    
    # ============================================================
    # NOTIFICATIONS
    # ============================================================
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/mark-read/<uuid:notification_id>/', views.mark_notification_read_view, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read_view, name='mark_all_read'),
    path('notifications/delete/<uuid:notification_id>/', views.delete_notification_view, name='delete_notification'),
    path('api/notifications/', views.get_notifications_api, name='api_notifications'),
    
    # ============================================================
    # WALLET & EARNINGS (NEW - Auto-split payment system)
    # ============================================================
    # Supplier Wallet & Earnings
    path('supplier/wallet/', views.supplier_wallet_view, name='supplier_wallet'),
    path('supplier/earnings/', views.supplier_earnings_view, name='supplier_earnings'),
    
    # Admin Commission Wallet
    path('admin/wallet/', views.admin_wallet_view, name='admin_wallet'),
    path('admin/commission/', views.admin_commission_view, name='admin_commission'),
    
    # Withdrawal Requests (Unified)
    path('wallet/withdraw/', views.request_wallet_withdrawal_view, name='request_withdrawal'),
    path('wallet/withdraw/process/<uuid:withdrawal_id>/', views.process_withdrawal_request_view, name='process_withdrawal'),
    
    # ============================================================
    # ACTIVITY LOGS & REPORTS (Admin only)
    # ============================================================
    path('admin/logs/', views.activity_logs_view, name='activity_logs'),
    path('admin/reports/', views.reports_view, name='reports'),
    
    # ============================================================
    # SETTINGS
    # ============================================================
    path('settings/', views.dashboard_settings_view, name='settings'),
]