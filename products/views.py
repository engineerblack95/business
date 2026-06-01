from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, F
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from decimal import Decimal

from .models import Product, Category, ProductReview, Wishlist, ProductViewHistory
from .forms import (
    ProductForm, ProductApprovalForm, ProductReviewForm, 
    ProductSearchForm, ProductStockUpdateForm
)
from .filters import ProductFilter
from accounts.decorators import role_required, permission_required
from accounts.models import User
from notifications.utils.notification_service import NotificationService


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def product_list_view(request):
    """Public product listing with search and filters"""
    
    # DEBUG: Print counts to console to see what's happening
    total_products = Product.objects.count()
    approved_products = Product.objects.filter(status='approved').count()
    pending_products = Product.objects.filter(status='pending_approval').count()
    draft_products = Product.objects.filter(status='draft').count()
    in_stock_products = Product.objects.filter(exact_quantity__gt=0).count()
    out_of_stock_products = Product.objects.filter(exact_quantity=0).count()
    
    print(f"=== PRODUCT DEBUG ===")
    print(f"Total products: {total_products}")
    print(f"Approved products: {approved_products}")
    print(f"Pending products: {pending_products}")
    print(f"Draft products: {draft_products}")
    print(f"In stock products: {in_stock_products}")
    print(f"Out of stock products: {out_of_stock_products}")
    print(f"====================")
    
    # Show all approved products, even if out of stock
    products = Product.objects.filter(
        status='approved'
    ).select_related('category', 'owner')
    
    # If no approved products found, show a warning
    if products.count() == 0 and total_products > 0:
        print(f"WARNING: No approved products found! Run this command to fix:")
        print(f"python manage.py shell -c 'from products.models import Product; Product.objects.update(status=\"approved\")'")
    elif products.count() == 0:
        print(f"INFO: No products in database yet. Add some products.")
    
    # Apply filters
    product_filter = ProductFilter(request.GET, queryset=products)
    products = product_filter.qs
    
    # Apply sorting
    sort_by = request.GET.get('sort_by', 'newest')
    if sort_by == 'price_low':
        products = products.order_by('final_price')
    elif sort_by == 'price_high':
        products = products.order_by('-final_price')
    elif sort_by == 'popular':
        products = products.order_by('-sales_count', '-views_count')
    elif sort_by == 'rating':
        products = products.order_by('-rating', '-rating_count')
    else:  # newest
        products = products.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for sidebar
    categories = Category.objects.filter(is_active=True, parent__isnull=True)
    
    context = {
        'products': page_obj,
        'categories': categories,
        'filter': product_filter,
        'sort_by': sort_by,
        'total_count': products.count(),
    }
    return render(request, 'products/list.html', context)


def product_detail_view(request, slug):
    """Product detail page with stock visibility logic"""
    
    try:
        product = get_object_or_404(
            Product.objects.select_related('category', 'owner'),
            slug=slug
        )
        # If product is not approved, only show to admin/supplier owners
        if product.status != 'approved':
            if not request.user.is_authenticated or (request.user.role != 'admin' and request.user != product.owner):
                messages.error(request, 'This product is not available yet.')
                return redirect('products:list')
    except:
        raise
    
    # Increment view count
    product.views_count += 1
    product.save()
    
    # FIXED: Ensure session exists before creating ProductViewHistory
    if not request.session.session_key:
        request.session.save()
    
    # Track view for analytics - with proper session_key
    ProductViewHistory.objects.create(
        product=product,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key,
        ip_address=get_client_ip(request)
    )
    
    # Get stock label based on user role
    stock_label = product.get_stock_label(request.user if request.user.is_authenticated else None)
    stock_badge_class = product.get_stock_badge_class()
    
    # Get related products (same category)
    related_products = Product.objects.filter(
        category=product.category,
        status='approved'
    ).exclude(id=product.id)[:8]
    
    # Get reviews
    reviews = product.reviews.filter(is_approved=True).select_related('customer')
    
    # Check if product is in user's wishlist
    in_wishlist = False
    if request.user.is_authenticated and request.user.role == 'customer':
        in_wishlist = Wishlist.objects.filter(
            customer=request.user,
            product=product
        ).exists()
    
    # Review form
    review_form = ProductReviewForm()
    
    context = {
        'product': product,
        'stock_label': stock_label,
        'stock_badge_class': stock_badge_class,
        'related_products': related_products,
        'reviews': reviews,
        'in_wishlist': in_wishlist,
        'review_form': review_form,
        'is_supplier_product': product.is_supplier_product,
        'owner_name': product.get_owner_name_for_display(),
    }
    return render(request, 'products/detail.html', context)


@login_required
@role_required(['supplier'])
def supplier_product_create_view(request):
    """Supplier creates new product (pending approval)"""
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.owner = request.user
            product.is_supplier_product = True
            product.status = 'pending_approval'
            product.approval_status = 'pending_approval'
            product.save()
            
            # Notify all admins about new product pending approval
            admins = User.objects.filter(role='admin')
            for admin in admins:
                NotificationService.create_notification(
                    user=admin,
                    title="New Product Pending Approval",
                    message=f"{getattr(request.user, 'business_name', request.user.email)} has submitted a new product: {product.name}",
                    notification_type='product',
                    priority='high',
                    link='/products/admin/approve/'
                )
            
            messages.success(request, 'Product submitted for admin approval. You will be notified once approved.')
            return redirect('products:supplier_products')
    else:
        form = ProductForm()
    
    return render(request, 'products/create.html', {'form': form})


@login_required
@role_required(['admin'])
def admin_product_approve_list_view(request):
    """Admin view all pending products for approval"""
    
    pending_products = Product.objects.filter(
        status='pending_approval'
    ).select_related('owner', 'category').order_by('-created_at')
    
    # Also show draft products that need attention
    draft_products = Product.objects.filter(
        status='draft'
    ).select_related('owner', 'category').order_by('-created_at')
    
    context = {
        'products': pending_products,
        'draft_products': draft_products,
        'total_pending': pending_products.count(),
        'total_draft': draft_products.count(),
    }
    return render(request, 'products/approve_list.html', context)


@login_required
@role_required(['admin'])
def admin_product_approve_view(request, product_id):
    """Admin approve or reject product"""
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = ProductApprovalForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save(commit=False)
            product.approved_by = request.user
            product.approved_at = timezone.now()
            
            if product.status == 'approved':
                product.approval_status = 'approved'
                messages.success(request, f'Product "{product.name}" has been approved.')
                
                # Notify the supplier about approval
                if product.is_supplier_product:
                    NotificationService.create_notification(
                        user=product.owner,
                        title=f"Product Approved: {product.name}",
                        message=f"Your product '{product.name}' has been approved and is now live on the platform.",
                        notification_type='product',
                        priority='medium',
                        link=f'/products/{product.slug}/'
                    )
                
            elif product.status == 'rejected':
                product.approval_status = 'rejected'
                messages.warning(request, f'Product "{product.name}" has been rejected.')
                
                # Notify the supplier about rejection
                if product.is_supplier_product:
                    NotificationService.create_notification(
                        user=product.owner,
                        title=f"Product Rejected: {product.name}",
                        message=f"Your product '{product.name}' was rejected. Please review and resubmit.",
                        notification_type='product',
                        priority='high',
                        link='/products/supplier/products/'
                    )
            
            product.save()
            return redirect('products:admin_approve_list')
    else:
        form = ProductApprovalForm(instance=product)
    
    return render(request, 'products/approve_product.html', {
        'form': form,
        'product': product
    })


@login_required
@role_required(['admin'])
def admin_quick_approve_all_view(request):
    """Admin quick approve all pending products (debug only)"""
    
    if request.method == 'POST':
        count = Product.objects.filter(status='pending_approval').update(
            status='approved',
            approval_status='approved',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        messages.success(request, f'Approved {count} products.')
        return redirect('products:admin_approve_list')
    
    return redirect('products:admin_approve_list')


@login_required
@role_required(['supplier'])
def supplier_products_view(request):
    """Supplier view their own products with exact stock"""
    
    products = Product.objects.filter(
        owner=request.user
    ).select_related('category').order_by('-created_at')
    
    context = {
        'products': products,
        'total_products': products.count(),
        'pending_count': products.filter(status='pending_approval').count(),
        'approved_count': products.filter(status='approved').count(),
        'rejected_count': products.filter(status='rejected').count(),
        'out_of_stock_count': products.filter(exact_quantity=0).count(),
        'draft_count': products.filter(status='draft').count(),
    }
    return render(request, 'products/supplier_products.html', context)


@login_required
@role_required(['supplier'])
def supplier_product_update_view(request, product_id):
    """Supplier update their product (resets approval status)"""
    
    product = get_object_or_404(Product, id=product_id, owner=request.user)
    
    if product.status == 'approved':
        messages.warning(request, 'Editing an approved product will require re-approval from admin.')
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save(commit=False)
            # Reset approval status
            if product.status == 'approved':
                product.status = 'pending_approval'
                product.approval_status = 'pending_approval'
                product.approved_by = None
                product.approved_at = None
            product.save()
            
            # Notify admins about product update pending re-approval
            admins = User.objects.filter(role='admin')
            for admin in admins:
                NotificationService.create_notification(
                    user=admin,
                    title="Product Update Pending Approval",
                    message=f"{getattr(request.user, 'business_name', request.user.email)} has updated product: {product.name}",
                    notification_type='product',
                    priority='medium',
                    link='/products/admin/approve/'
                )
            
            messages.success(request, 'Product updated successfully. It will be reviewed by admin.')
            return redirect('products:supplier_products')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'products/update.html', {
        'form': form,
        'product': product
    })


@login_required
@role_required(['supplier'])
def supplier_product_stock_update_view(request, product_id):
    """Supplier update exact stock quantity"""
    
    product = get_object_or_404(Product, id=product_id, owner=request.user)
    
    if request.method == 'POST':
        form = ProductStockUpdateForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Stock updated to {product.exact_quantity} units')
            
            # Notify admin about low stock if applicable
            if product.is_low_stock():
                admins = User.objects.filter(role='admin')
                for admin in admins:
                    NotificationService.create_notification(
                        user=admin,
                        title=f"Low Stock Alert: {product.name}",
                        message=f"Product '{product.name}' from {getattr(product.owner, 'business_name', product.owner.email)} has only {product.exact_quantity} units remaining.",
                        notification_type='alert',
                        priority='high',
                        link=f'/dashboard/admin/products/'
                    )
            
            return redirect('products:supplier_products')
    else:
        form = ProductStockUpdateForm(instance=product)
    
    return render(request, 'products/update_stock.html', {
        'form': form,
        'product': product
    })


@login_required
def add_review_view(request, product_id):
    """Customer add product review"""
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.customer = request.user
            
            # Check if user has purchased this product
            from orders.models import OrderItem
            has_purchased = OrderItem.objects.filter(
                order__customer=request.user,
                product=product,
                order__payment_status='paid'
            ).exists()
            
            review.is_verified_purchase = has_purchased
            review.save()
            
            messages.success(request, 'Thank you for your review!')
            return redirect('products:detail', slug=product.slug)
    else:
        form = ProductReviewForm()
    
    return render(request, 'products/add_review.html', {
        'form': form,
        'product': product
    })


@login_required
@role_required(['customer'])
def add_to_wishlist_view(request, product_id):
    """Add product to wishlist"""
    
    product = get_object_or_404(Product, id=product_id)
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        customer=request.user,
        product=product
    )
    
    if created:
        messages.success(request, f'{product.name} added to your wishlist')
    else:
        messages.info(request, f'{product.name} is already in your wishlist')
    
    return redirect('products:detail', slug=product.slug)


@login_required
@role_required(['customer'])
def wishlist_view(request):
    """View customer wishlist"""
    
    wishlist_items = Wishlist.objects.filter(
        customer=request.user
    ).select_related('product').order_by('-added_at')
    
    context = {
        'wishlist_items': wishlist_items,
        'total_items': wishlist_items.count(),
    }
    return render(request, 'products/wishlist.html', context)


@login_required
@role_required(['customer'])
def remove_from_wishlist_view(request, product_id):
    """Remove product from wishlist"""
    
    Wishlist.objects.filter(
        customer=request.user,
        product_id=product_id
    ).delete()
    
    messages.success(request, 'Product removed from wishlist')
    return redirect('products:wishlist')


def search_products_view(request):
    """AJAX search endpoint for products"""
    
    query = request.GET.get('q', '')
    products = []
    
    if query:
        product_queryset = Product.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query) |
            Q(brand__icontains=query),
            status='approved'
        )[:10]
        
        products = [{
            'id': str(p.id),
            'name': p.name,
            'final_price': float(p.final_price),
            'image': p.main_image.url if p.main_image else None,
            'slug': p.slug,
            'stock_label': p.get_stock_label(),
        } for p in product_queryset]
    
    return JsonResponse({'products': products})


def category_products_view(request, slug):
    """View products by category"""
    
    category = get_object_or_404(Category, slug=slug, is_active=True)
    
    products = Product.objects.filter(
        category=category,
        status='approved'
    ).order_by('-created_at')
    
    context = {
        'category': category,
        'products': products,
        'total_count': products.count(),
    }
    return render(request, 'products/category_list.html', context)


def high_performance_products_view(request):
    """View high-performance products (top selling/rating)"""
    
    # Get top products by sales and rating
    products = Product.objects.filter(
        status='approved'
    ).annotate(
        performance_score=F('sales_count') * 2 + F('rating') * 10 + F('views_count') * 0.5
    ).order_by('-performance_score')[:20]
    
    context = {
        'products': products,
        'title': 'High Performance Products',
    }
    return render(request, 'products/high_performance.html', context)