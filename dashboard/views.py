from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse

from accounts.decorators import role_required, permission_required
from .utils.analytics import DashboardAnalytics
from .utils.notifications import NotificationManager
from .models import UserActivityLog, DashboardPreference
from notifications.models import Notification
from .forms import TeamMemberForm, NotificationFilterForm, ProductQuickEditForm

from products.models import Product, Category
from orders.models import Order, OrderItem, CommissionEarning, WithdrawalRequest
from accounts.models import User


@login_required
def dashboard_redirect_view(request):
    """Redirect user to their appropriate dashboard"""
    # Check supplier first (approved suppliers)
    if request.user.role == 'supplier' or request.user.is_approved_supplier:
        return redirect('dashboard:supplier')
    elif request.user.role == 'admin':
        return redirect('dashboard:admin')
    elif request.user.role == 'team_member':
        return redirect('dashboard:team')
    else:
        return redirect('dashboard:customer')


@login_required
@role_required(['admin'])
def admin_dashboard_view(request):
    """Admin main dashboard"""
    
    analytics = DashboardAnalytics.get_admin_analytics()
    
    # Get unread notifications for admin
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # Get recent supplier applications (from SupplierApplication model)
    from suppliers.models import SupplierApplication
    recent_applications = SupplierApplication.objects.filter(
        status__in=['pending', 'reviewing']
    ).select_related('supplier').order_by('-created_at')[:5]
    
    # Get recent withdrawal requests
    recent_withdrawals = WithdrawalRequest.objects.filter(
        admin=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        'analytics': analytics,
        'unread_notifications': unread_notifications,
        'recent_suppliers': recent_applications,
        'recent_withdrawals': recent_withdrawals,
        'section': 'overview',
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def supplier_dashboard_view(request):
    """Supplier main dashboard"""
    
    # Check if user is a supplier
    if request.user.role != 'supplier' and not request.user.is_approved_supplier:
        messages.error(request, 'Access denied. You are not a registered supplier.')
        return redirect('dashboard:customer')
    
    analytics = DashboardAnalytics.get_supplier_analytics(request.user)
    
    # Get unread notifications
    unread_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # Get recent products
    recent_products = Product.objects.filter(owner=request.user).order_by('-created_at')[:5]
    
    # Get recent orders for supplier's products
    recent_orders = Order.objects.filter(
        items__product__owner=request.user
    ).distinct().order_by('-created_at')[:10]
    
    context = {
        'analytics': analytics,
        'unread_notifications': unread_notifications,
        'recent_products': recent_products,
        'recent_orders': recent_orders,
        'section': 'overview',
    }
    return render(request, 'dashboard/supplier_dashboard.html', context)


@login_required
def customer_dashboard_view(request):
    """Customer main dashboard"""
    
    analytics = DashboardAnalytics.get_customer_analytics(request.user)
    
    # Get recent orders
    recent_orders = Order.objects.filter(customer=request.user).order_by('-created_at')[:10]
    
    # Get wishlist items
    from products.models import Wishlist
    wishlist_items = Wishlist.objects.filter(
        customer=request.user
    ).select_related('product')[:8]
    
    context = {
        'analytics': analytics,
        'recent_orders': recent_orders,
        'wishlist_items': wishlist_items,
        'section': 'overview',
    }
    return render(request, 'dashboard/customer_dashboard.html', context)


@login_required
@role_required(['admin', 'team_member'])
def team_dashboard_view(request):
    """Team member dashboard (limited permissions)"""
    
    # Check permissions
    if request.user.role == 'team_member':
        permissions = request.user.team_permissions
        
        # Show only allowed sections
        context = {
            'permissions': permissions,
            'section': 'overview',
        }
        
        # Load data based on permissions
        if permissions.get('can_view_orders'):
            context['recent_orders'] = Order.objects.order_by('-created_at')[:10]
        
        if permissions.get('can_view_products'):
            context['recent_products'] = Product.objects.order_by('-created_at')[:10]
        
        return render(request, 'dashboard/team_dashboard.html', context)
    
    # Admin fallback
    return redirect('dashboard:admin')


@login_required
@role_required(['admin'])
def manage_team_members_view(request):
    """Admin manage team members"""
    
    if request.method == 'POST':
        form = TeamMemberForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Send notification to new team member
            NotificationManager.send_notification(
                user=user,
                title="Welcome to the Team!",
                message=f"You have been added as a team member at HerosTechnology.",
                notification_type='system',
                link='/dashboard/team/'
            )
            
            messages.success(request, f'Team member {user.email} added successfully.')
            return redirect('dashboard:manage_team')
    else:
        form = TeamMemberForm()
    
    # Get all team members
    team_members = User.objects.filter(role='team_member').order_by('-date_joined')
    
    context = {
        'form': form,
        'team_members': team_members,
        'section': 'team',
    }
    return render(request, 'dashboard/manage_team.html', context)


@login_required
@role_required(['admin'])
def edit_team_member_view(request, user_id):
    """Admin edit team member permissions"""
    
    team_member = get_object_or_404(User, id=user_id, role='team_member')
    
    if request.method == 'POST':
        form = TeamMemberForm(request.POST, instance=team_member)
        if form.is_valid():
            form.save()
            messages.success(request, f'Team member {team_member.email} updated successfully.')
            return redirect('dashboard:manage_team')
    else:
        # Set initial permissions
        initial_permissions = [perm for perm, value in team_member.team_permissions.items() if value]
        form = TeamMemberForm(instance=team_member, initial={'permissions': initial_permissions})
    
    context = {
        'form': form,
        'team_member': team_member,
        'section': 'team',
    }
    return render(request, 'dashboard/edit_team_member.html', context)


@login_required
@role_required(['admin'])
def remove_team_member_view(request, user_id):
    """Admin remove team member"""
    
    team_member = get_object_or_404(User, id=user_id, role='team_member')
    
    if request.method == 'POST':
        team_member.role = 'customer'
        team_member.team_permissions = {}
        team_member.save()
        messages.success(request, f'Team member {team_member.email} removed.')
    
    return redirect('dashboard:manage_team')


@login_required
def notifications_view(request):
    """View all notifications"""
    
    notifications = Notification.objects.filter(user=request.user)
    
    # Apply filters
    filter_form = NotificationFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('notification_type'):
            notifications = notifications.filter(notification_type=filter_form.cleaned_data['notification_type'])
        if filter_form.cleaned_data.get('is_read') == 'true':
            notifications = notifications.filter(is_read=False)
        elif filter_form.cleaned_data.get('is_read') == 'false':
            notifications = notifications.filter(is_read=True)
        if filter_form.cleaned_data.get('date_from'):
            notifications = notifications.filter(created_at__date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            notifications = notifications.filter(created_at__date__lte=filter_form.cleaned_data['date_to'])
    
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'notifications': page_obj,
        'filter_form': filter_form,
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'dashboard/notifications.html', context)


@login_required
def mark_notification_read_view(request, notification_id):
    """Mark single notification as read"""
    
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('dashboard:notifications')


@login_required
def mark_all_notifications_read_view(request):
    """Mark all notifications as read"""
    
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    messages.success(request, 'All notifications marked as read.')
    
    return redirect('dashboard:notifications')


@login_required
def delete_notification_view(request, notification_id):
    """Delete a notification"""
    
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    
    return redirect('dashboard:notifications')


@login_required
def get_notifications_api(request):
    """API endpoint for real-time notifications"""
    
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:10]
    
    notifications_data = [{
        'id': str(n.id),
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'priority': n.priority,
        'link': n.link,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S'),
    } for n in notifications]
    
    return JsonResponse({
        'count': notifications.count(),
        'notifications': notifications_data
    })


@login_required
@role_required(['admin'])
def manage_products_dashboard(request):
    """Admin product management dashboard"""
    
    products = Product.objects.select_related('owner', 'category').order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        products = products.filter(status=status)
    
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'section': 'products',
        'status_filter': status,
    }
    return render(request, 'dashboard/manage_products.html', context)


@login_required
@role_required(['admin', 'supplier'])
def quick_stock_update_view(request):
    """Quick stock update from dashboard"""
    
    if request.method == 'POST':
        form = ProductQuickEditForm(request.POST)
        if form.is_valid():
            product_id = form.cleaned_data['product_id']
            product = get_object_or_404(Product, id=product_id)
            
            # Check permission
            if request.user.role == 'supplier' and product.owner != request.user:
                return JsonResponse({'success': False, 'error': 'Permission denied'})
            
            if form.cleaned_data.get('exact_quantity') is not None:
                product.exact_quantity = form.cleaned_data['exact_quantity']
                product.save()
                
                # Check low stock alert
                if product.is_low_stock():
                    NotificationManager.notify_low_stock(product)
            
            if form.cleaned_data.get('base_price') is not None:
                product.base_price = form.cleaned_data['base_price']
                product.save()
            
            return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@role_required(['admin'])
def manage_suppliers_view(request):
    """Admin manage suppliers - shows pending applications and approved suppliers"""
    
    from suppliers.models import SupplierApplication
    
    show_pending = request.GET.get('pending', 'false') == 'true'
    
    if show_pending:
        # Show pending applications from SupplierApplication model
        pending_applications = SupplierApplication.objects.filter(
            status__in=['pending', 'reviewing']
        ).select_related('supplier')
        
        # Extract the users from pending applications
        supplier_ids = [app.supplier.id for app in pending_applications]
        suppliers = User.objects.filter(id__in=supplier_ids) if supplier_ids else User.objects.none()
        
        # Add the application data as an attribute for use in template
        for supplier in suppliers:
            if hasattr(supplier, 'supplier_application'):
                supplier.application = supplier.supplier_application
            else:
                try:
                    supplier.application = SupplierApplication.objects.get(supplier=supplier)
                except SupplierApplication.DoesNotExist:
                    supplier.application = None
        
        suppliers = suppliers.order_by('-date_joined')
        
    else:
        # Show approved suppliers
        suppliers = User.objects.filter(
            role='supplier', 
            is_approved_supplier=True
        ).select_related('supplier_profile').order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(suppliers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'suppliers': page_obj,
        'show_pending': show_pending,
        'section': 'suppliers',
    }
    return render(request, 'dashboard/manage_suppliers.html', context)


@login_required
@role_required(['admin'])
def approve_supplier_view(request, user_id):
    """Admin approve supplier application"""
    
    from suppliers.models import SupplierApplication, SupplierProfile
    from notifications.utils.notification_service import NotificationService
    
    supplier = get_object_or_404(User, id=user_id)
    
    # Get the application
    try:
        application = SupplierApplication.objects.get(supplier=supplier, status__in=['pending', 'reviewing'])
    except SupplierApplication.DoesNotExist:
        messages.error(request, 'No pending application found for this supplier.')
        return redirect('dashboard:manage_suppliers')
    
    if request.method == 'POST':
        # Update user role and approval status
        supplier.role = 'supplier'
        supplier.is_approved_supplier = True
        supplier.business_name = application.business_name
        # tax_id is on User model, not on SupplierProfile
        if application.tax_id:
            supplier.tax_id = application.tax_id
        supplier.save()
        
        # Update application status
        application.status = 'approved'
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.approved_at = timezone.now()
        application.save()
        
        # Create or update supplier profile - REMOVED tax_id from here
        profile, created = SupplierProfile.objects.get_or_create(
            supplier=supplier,
            defaults={
                'business_name': application.business_name,
                'business_type': application.business_type,
                'business_phone': application.business_phone,
                'business_email': application.business_email,
                'business_address': application.business_address,
                'business_city': application.business_city,
                'business_country': application.business_country,
                'website': application.website,
                'years_in_business': application.years_in_business,
                'verification_status': 'verified',
                'is_active': True
            }
        )
        
        if not created:
            # Update existing profile
            profile.business_name = application.business_name
            profile.business_type = application.business_type
            profile.business_phone = application.business_phone
            profile.business_email = application.business_email
            profile.business_address = application.business_address
            profile.business_city = application.business_city
            profile.business_country = application.business_country
            profile.website = application.website
            profile.years_in_business = application.years_in_business
            profile.verification_status = 'verified'
            profile.save()
        
        # Send notification to supplier
        NotificationService.create_notification(
            user=supplier,
            title="Supplier Application Approved! 🎉",
            message="Congratulations! Your supplier application has been approved. You can now start adding products.",
            notification_type='supplier',
            priority='high',
            link='/dashboard/supplier/'
        )
        
        messages.success(request, f'Supplier {supplier.email} approved successfully.')
    
    return redirect(f"{reverse('dashboard:manage_suppliers')}?pending=true")


@login_required
@role_required(['admin'])
def reject_supplier_view(request, user_id):
    """Admin reject supplier application"""
    
    from suppliers.models import SupplierApplication
    from notifications.utils.notification_service import NotificationService
    
    supplier = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Not specified')
        
        # Get the application
        try:
            application = SupplierApplication.objects.get(supplier=supplier, status__in=['pending', 'reviewing'])
            application.status = 'rejected'
            application.rejection_reason = reason
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
        except SupplierApplication.DoesNotExist:
            pass
        
        # Change user role back to customer if needed
        if supplier.role == 'supplier':
            supplier.role = 'customer'
            supplier.is_approved_supplier = False
            supplier.save()
        
        # Send rejection notification
        NotificationService.create_notification(
            user=supplier,
            title="Supplier Application Update",
            message=f"Your supplier application has been reviewed. Unfortunately, it was not approved at this time.\nReason: {reason}",
            notification_type='supplier',
            priority='medium',
            link='/suppliers/apply/'
        )
        
        messages.success(request, f'Supplier application rejected.')
    
    return redirect(f"{reverse('dashboard:manage_suppliers')}?pending=true")


@login_required
@role_required(['admin'])
def activity_logs_view(request):
    """View system activity logs"""
    
    logs = UserActivityLog.objects.select_related('user').order_by('-created_at')
    
    # Apply filters
    activity_type = request.GET.get('type')
    if activity_type:
        logs = logs.filter(activity_type=activity_type)
    
    user_id = request.GET.get('user')
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get users for filter dropdown
    users = User.objects.all().order_by('email')
    
    context = {
        'logs': page_obj,
        'users': users,
        'selected_type': activity_type,
        'selected_user': user_id,
        'section': 'logs',
    }
    return render(request, 'dashboard/activity_logs.html', context)


@login_required
@role_required(['admin'])
def reports_view(request):
    """Generate and view reports"""
    
    from datetime import timedelta
    
    # Get date range
    date_range = request.GET.get('range', 'month')
    
    if date_range == 'today':
        start_date = timezone.now().date()
        end_date = start_date
    elif date_range == 'week':
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
    elif date_range == 'month':
        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date()
    elif date_range == 'year':
        start_date = timezone.now().date() - timedelta(days=365)
        end_date = timezone.now().date()
    else:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
    
    # Sales report
    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        payment_status__in=['simulated', 'paid']
    )
    
    total_revenue = orders.aggregate(total=Sum('grand_total'))['total'] or 0
    total_orders = orders.count()
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    
    # Top products
    top_products = Product.objects.annotate(
        total_sold=Sum('order_items__quantity')
    ).order_by('-total_sold')[:10]
    
    # Top customers
    top_customers = User.objects.filter(
        role='customer',
        orders__payment_status__in=['simulated', 'paid']
    ).annotate(
        total_spent=Sum('orders__grand_total'),
        order_count=Count('orders')
    ).order_by('-total_spent')[:10]
    
    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'top_products': top_products,
        'top_customers': top_customers,
        'start_date': start_date,
        'end_date': end_date,
        'date_range': date_range,
        'section': 'reports',
    }
    return render(request, 'dashboard/reports.html', context)


@login_required
def dashboard_settings_view(request):
    """User dashboard settings"""
    
    # Get or create preferences
    prefs, created = DashboardPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        prefs.theme = request.POST.get('theme', 'light')
        prefs.email_notifications = request.POST.get('email_notifications') == 'on'
        prefs.push_notifications = request.POST.get('push_notifications') == 'on'
        prefs.save()
        
        messages.success(request, 'Dashboard settings updated successfully.')
        return redirect('dashboard:settings')
    
    context = {
        'prefs': prefs,
        'section': 'settings',
    }
    return render(request, 'dashboard/settings.html', context)

@login_required
@role_required(['admin'])
def reports_view(request):
    """Generate and view reports"""
    
    from datetime import timedelta
    from django.utils import timezone
    
    # Get date range
    date_range = request.GET.get('range', 'month')
    
    # Initialize dates
    start_date = None
    end_date = None
    
    if date_range == 'today':
        start_date = timezone.now().date()
        end_date = start_date
    elif date_range == 'week':
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
    elif date_range == 'month':
        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date()
    elif date_range == 'year':
        start_date = timezone.now().date() - timedelta(days=365)
        end_date = timezone.now().date()
    elif date_range == 'custom':
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        # Validate that start_date and end_date are provided
        if start_date_str and end_date_str:
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to last 30 days if no dates provided
            start_date = timezone.now().date() - timedelta(days=30)
            end_date = timezone.now().date()
    
    # Ensure dates are valid
    if not start_date or not end_date:
        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date()
    
    # Sales report
    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        payment_status__in=['simulated', 'paid']
    )
    
    total_revenue = orders.aggregate(total=Sum('grand_total'))['total'] or 0
    total_orders = orders.count()
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    
    # Top products
    top_products = Product.objects.annotate(
        total_sold=Sum('order_items__quantity')
    ).order_by('-total_sold')[:10]
    
    # Top customers
    top_customers = User.objects.filter(
        role='customer',
        orders__payment_status__in=['simulated', 'paid']
    ).annotate(
        total_spent=Sum('orders__grand_total'),
        order_count=Count('orders')
    ).order_by('-total_spent')[:10]
    
    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'top_products': top_products,
        'top_customers': top_customers,
        'start_date': start_date,
        'end_date': end_date,
        'date_range': date_range,
        'section': 'reports',
    }
    return render(request, 'dashboard/reports.html', context)