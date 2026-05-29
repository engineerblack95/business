from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment methods
    path('methods/', views.payment_methods_view, name='methods'),
    
    # Payment processing
    path('initiate/<uuid:order_id>/', views.initiate_payment_view, name='initiate_payment'),
    path('status/<str:transaction_id>/', views.payment_status_view, name='payment_status'),
    path('success/<str:transaction_id>/', views.payment_success_view, name='payment_success'),
    path('history/', views.payment_history_view, name='payment_history'),
    path('transaction/<str:transaction_id>/', views.transaction_detail_view, name='transaction_detail'),
    
    # Commission (Admin)
    path('commission/', views.commission_dashboard_view, name='commission_dashboard'),
    path('withdrawals/', views.withdrawal_history_view, name='withdrawal_history'),
    path('withdrawal/<uuid:withdrawal_id>/process/', views.process_withdrawal_view, name='process_withdrawal'),
    
    # Supplier payouts (Admin)
    path('supplier-payouts/', views.supplier_payouts_view, name='supplier_payouts'),
    
    # Supplier payouts (Supplier)
    path('my-payouts/', views.my_payouts_view, name='my_payouts'),
    
    # Webhooks
    path('webhook/<str:provider>/', views.payment_webhook_view, name='webhook'),
]