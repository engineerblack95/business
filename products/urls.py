from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # ============================================================
    # PUBLIC VIEWS
    # ============================================================
    path('', views.product_list_view, name='list'),
    path('search/', views.search_products_view, name='search'),
    path('high-performance/', views.high_performance_products_view, name='high_performance'),
    
    # ============================================================
    # CATEGORY VIEW - FIXED to use the correct view
    # ============================================================
    path('category/<slug:slug>/', views.category_products_view, name='category'),
    
    # ============================================================
    # CUSTOMER VIEWS
    # ============================================================
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<uuid:product_id>/', views.add_to_wishlist_view, name='add_to_wishlist'),
    path('wishlist/remove/<uuid:product_id>/', views.remove_from_wishlist_view, name='remove_from_wishlist'),
    path('review/add/<uuid:product_id>/', views.add_review_view, name='add_review'),
    
    # ============================================================
    # SUPPLIER VIEWS
    # ============================================================
    path('supplier/products/', views.supplier_products_view, name='supplier_products'),
    path('supplier/create/', views.supplier_product_create_view, name='supplier_create'),
    path('supplier/update/<uuid:product_id>/', views.supplier_product_update_view, name='supplier_update'),
    path('supplier/stock/<uuid:product_id>/', views.supplier_product_stock_update_view, name='supplier_stock_update'),
    
    # ============================================================
    # ADMIN VIEWS
    # ============================================================
    path('admin/approve/', views.admin_product_approve_list_view, name='admin_approve_list'),
    path('admin/approve/<uuid:product_id>/', views.admin_product_approve_view, name='admin_approve'),
    path('admin/approve-all/', views.admin_quick_approve_all_view, name='admin_approve_all'),
    
    # ============================================================
    # PRODUCT DETAIL - MUST BE LAST
    # ============================================================
    path('<slug:slug>/', views.product_detail_view, name='detail'),
]