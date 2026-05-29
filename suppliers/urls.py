from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Supplier application
    path('apply/', views.apply_supplier_view, name='apply'),
    path('application/status/', views.application_status_view, name='application_status'),
    
    # Supplier profile
    path('profile/', views.supplier_profile_view, name='profile'),
    
    # Payouts
    path('payouts/', views.payout_history_view, name='payout_history'),
    
    # Performance
    path('performance/', views.performance_report_view, name='performance_report'),
    
    # Admin views
    path('admin/applications/', views.review_applications_view, name='review_applications'),
    path('admin/applications/<uuid:application_id>/', views.review_application_detail_view, name='review_application_detail'),
    path('admin/suppliers/', views.supplier_list_view, name='supplier_list'),
    path('admin/suppliers/<uuid:user_id>/', views.supplier_detail_view, name='supplier_detail'),
    
    # Document download
    path('documents/<uuid:application_id>/<str:doc_type>/', views.download_document_view, name='download_document'),
]