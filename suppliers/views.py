from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction, models
from django.utils import timezone
from django.db.models import Q, Sum, Avg, Count
from django.http import JsonResponse
from decimal import Decimal

from accounts.decorators import role_required, permission_required
from accounts.models import User
from .models import SupplierApplication, SupplierProfile, SupplierPayoutHistory, SupplierPerformanceMetric
from .forms import SupplierApplicationForm, SupplierApplicationReviewForm, SupplierProfileForm, SupplierFilterForm
from .utils.document_processor import DocumentProcessor, SupplierValidator
from notifications.utils.notification_service import NotificationService  # Use the correct notification service
from orders.utils.commission_calculator import SupplierPayoutCalculator
from orders.models import Order, OrderItem

from products.models import Product, Category


@login_required
def apply_supplier_view(request):
    """Customer applies to become a supplier"""
    
    # Check if already applied
    if hasattr(request.user, 'supplier_application'):
        application = request.user.supplier_application
        if application.status in ['pending', 'reviewing']:
            messages.warning(request, 'You already have a pending application.')
            return redirect('suppliers:application_status')
        elif application.status == 'approved':
            messages.info(request, 'You are already a registered supplier.')
            return redirect('dashboard:supplier')
    
    if request.method == 'POST':
        form = SupplierApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.supplier = request.user
            
            # Validate documents
            doc_errors = []
            for field in ['business_license', 'id_document']:
                file = getattr(application, field)
                if file:
                    errors = DocumentProcessor.validate_document(file)
                    if errors:
                        doc_errors.extend(errors)
            
            if doc_errors:
                for error in doc_errors:
                    messages.error(request, error)
                return render(request, 'suppliers/application_form.html', {'form': form})
            
            application.save()
            form.save_m2m()
            
            # Notify all admins about new application
            admins = User.objects.filter(role='admin')
            for admin in admins:
                NotificationService.create_notification(
                    user=admin,
                    title="New Supplier Application",
                    message=f"{request.user.email} has applied to become a supplier. Please review their application.",
                    notification_type='supplier',
                    priority='high',
                    link='/dashboard/admin/suppliers/?pending=true'
                )
            
            messages.success(request, 'Your supplier application has been submitted successfully! Our team will review it and contact you soon.')
            return redirect('suppliers:application_status')
    else:
        form = SupplierApplicationForm()
    
    return render(request, 'suppliers/application_form.html', {'form': form})


@login_required
def application_status_view(request):
    """View supplier application status"""
    
    try:
        application = request.user.supplier_application
    except SupplierApplication.DoesNotExist:
        messages.info(request, 'You have not submitted a supplier application yet.')
        return redirect('suppliers:apply')
    
    context = {
        'application': application,
    }
    return render(request, 'suppliers/application_status.html', context)


@login_required
@role_required(['admin'])
def review_applications_view(request):
    """Admin review supplier applications"""
    
    applications = SupplierApplication.objects.select_related('supplier').order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status', 'pending')
    if status:
        applications = applications.filter(status=status)
    
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'pending': SupplierApplication.objects.filter(status='pending').count(),
        'reviewing': SupplierApplication.objects.filter(status='reviewing').count(),
        'approved': SupplierApplication.objects.filter(status='approved').count(),
        'rejected': SupplierApplication.objects.filter(status='rejected').count(),
        'total': SupplierApplication.objects.count(),
    }
    
    context = {
        'applications': page_obj,
        'stats': stats,
        'current_status': status,
    }
    return render(request, 'suppliers/review_applications.html', context)


@login_required
@role_required(['admin'])
@transaction.atomic
def review_application_detail_view(request, application_id):
    """Admin review specific application in detail"""
    
    application = get_object_or_404(SupplierApplication, id=application_id)
    
    if request.method == 'POST':
        form = SupplierApplicationReviewForm(request.POST, instance=application)
        if form.is_valid():
            application = form.save()
            
            if application.status == 'approved':
                application.approve(request.user)
                
                # Notify the supplier about approval
                NotificationService.create_notification(
                    user=application.supplier,
                    title="Supplier Application Approved! 🎉",
                    message="Congratulations! Your supplier application has been approved. You can now start adding products.",
                    notification_type='supplier',
                    priority='high',
                    link='/dashboard/supplier/'
                )
                messages.success(request, f'Application approved. {application.supplier.email} is now a supplier.')
                
            elif application.status == 'rejected':
                application.reject(request.user, form.cleaned_data['rejection_reason'])
                
                # Notify the supplier about rejection
                NotificationService.create_notification(
                    user=application.supplier,
                    title="Supplier Application Update",
                    message=f"Your supplier application has been reviewed. Unfortunately, it was not approved at this time.\nReason: {application.rejection_reason}",
                    notification_type='supplier',
                    priority='medium',
                    link='/suppliers/apply/'
                )
                messages.warning(request, 'Application rejected.')
                
            elif application.status == 'additional_info':
                application.request_additional_info(request.user, form.cleaned_data['additional_info_request'])
                
                # Notify the supplier about additional info needed
                NotificationService.create_notification(
                    user=application.supplier,
                    title="Additional Information Required",
                    message=f"Please provide additional information for your supplier application: {application.additional_info_request}",
                    notification_type='supplier',
                    priority='high',
                    link='/suppliers/apply/'
                )
                messages.info(request, 'Requested additional information from supplier.')
            
            return redirect('suppliers:review_applications')
    else:
        form = SupplierApplicationReviewForm(instance=application)
    
    # Get document info
    documents = {
        'business_license': application.business_license,
        'id_document': application.id_document,
        'tax_clearance': application.tax_clearance,
        'bank_statement': application.bank_statement,
    }
    
    context = {
        'application': application,
        'form': form,
        'documents': documents,
    }
    return render(request, 'suppliers/review_application_detail.html', context)


@login_required
@role_required(['supplier'])
def supplier_profile_view(request):
    """Supplier view and edit profile"""
    
    profile, created = SupplierProfile.objects.get_or_create(
        supplier=request.user,
        defaults={
            'business_name': request.user.business_name or '',
            'business_phone': request.user.phone,
            'business_email': request.user.email,
            'business_address': '',
            'business_city': '',
            'business_country': 'Rwanda',
        }
    )
    
    if request.method == 'POST':
        form = SupplierProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('suppliers:profile')
    else:
        form = SupplierProfileForm(instance=profile)
    
    # Update metrics
    profile.update_metrics()
    
    context = {
        'form': form,
        'profile': profile,
        'total_products': Product.objects.filter(owner=request.user).count(),
        'pending_products': Product.objects.filter(owner=request.user, status='pending_approval').count(),
        'total_sales': profile.total_sales,
    }
    return render(request, 'suppliers/supplier_profile.html', context)


@login_required
@role_required(['admin'])
def supplier_list_view(request):
    """Admin view all suppliers"""
    
    suppliers = User.objects.filter(role='supplier', is_approved_supplier=True).select_related('supplier_profile')
    
    # Apply filters
    filter_form = SupplierFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('verification_status'):
            suppliers = suppliers.filter(supplier_profile__verification_status=filter_form.cleaned_data['verification_status'])
        
        if filter_form.cleaned_data.get('min_rating'):
            suppliers = suppliers.filter(supplier_profile__average_rating__gte=filter_form.cleaned_data['min_rating'])
        
        if filter_form.cleaned_data.get('search'):
            search = filter_form.cleaned_data['search']
            suppliers = suppliers.filter(
                Q(email__icontains=search) |
                Q(full_name__icontains=search) |
                Q(supplier_profile__business_name__icontains=search)
            )
    
    paginator = Paginator(suppliers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'suppliers': page_obj,
        'filter_form': filter_form,
        'total_suppliers': suppliers.count(),
    }
    return render(request, 'suppliers/supplier_list.html', context)


@login_required
@role_required(['admin'])
def supplier_detail_view(request, user_id):
    """Admin view supplier details"""
    
    supplier = get_object_or_404(User, id=user_id, role='supplier')
    
    # Get supplier stats
    products = Product.objects.filter(owner=supplier)
    total_products = products.count()
    total_sales = products.aggregate(total=Sum('sales_count'))['total'] or 0
    
    total_revenue = products.aggregate(
        total=Sum('final_price', filter=models.Q(order_items__order__payment_status__in=['simulated', 'paid']))
    )['total'] or 0
    
    # Get recent products
    recent_products = products.order_by('-created_at')[:10]
    
    # Get recent orders
    recent_orders = Order.objects.filter(
        items__product__owner=supplier
    ).distinct().order_by('-created_at')[:10]
    
    # Get payout history
    payouts = SupplierPayoutHistory.objects.filter(supplier=supplier).order_by('-created_at')[:10]
    
    context = {
        'supplier': supplier,
        'profile': supplier.supplier_profile if hasattr(supplier, 'supplier_profile') else None,
        'total_products': total_products,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'recent_products': recent_products,
        'recent_orders': recent_orders,
        'payouts': payouts,
    }
    return render(request, 'suppliers/supplier_detail.html', context)


@login_required
@role_required(['supplier'])
def payout_history_view(request):
    """Supplier view payout history"""
    
    payouts = SupplierPayoutHistory.objects.filter(
        supplier=request.user
    ).order_by('-created_at')
    
    paginator = Paginator(payouts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate totals
    total_paid = payouts.filter(status='completed').aggregate(total=Sum('net_amount'))['total'] or 0
    total_pending = payouts.filter(status='pending').aggregate(total=Sum('net_amount'))['total'] or 0
    
    context = {
        'payouts': page_obj,
        'total_paid': total_paid,
        'total_pending': total_pending,
    }
    return render(request, 'suppliers/payout_history.html', context)


@login_required
@role_required(['supplier'])
def performance_report_view(request):
    """Supplier view performance report"""
    
    from suppliers.utils.supplier_validator import SupplierPerformanceCalculator
    
    # Calculate performance score
    score = SupplierPerformanceCalculator.calculate_performance_score(request.user)
    tier_info = SupplierPerformanceCalculator.get_supplier_tier(score)
    
    # Get weekly report
    weekly = SupplierPerformanceCalculator.get_weekly_report(request.user)
    
    # Get monthly metrics
    from datetime import timedelta
    
    monthly_items = OrderItem.objects.filter(
        product__owner=request.user,
        order__created_at__gte=timezone.now() - timedelta(days=30),
        order__payment_status__in=['simulated', 'paid']
    )
    
    monthly_sales = monthly_items.aggregate(total=Sum('final_price'))['total'] or 0
    monthly_units = monthly_items.aggregate(total=Sum('quantity'))['total'] or 0
    
    # Top selling products
    top_products = Product.objects.filter(owner=request.user).order_by('-sales_count')[:5]
    
    context = {
        'score': score,
        'tier': tier_info['tier'],
        'badge': tier_info['badge'],
        'commission_rate': tier_info['commission_rate'],
        'weekly': weekly,
        'monthly_sales': monthly_sales,
        'monthly_units': monthly_units,
        'top_products': top_products,
    }
    return render(request, 'suppliers/performance_report.html', context)


@login_required
def download_document_view(request, application_id, doc_type):
    """Download supplier application document"""
    
    application = get_object_or_404(SupplierApplication, id=application_id)
    
    # Check permissions
    if request.user.role != 'admin' and request.user != application.supplier:
        messages.error(request, 'Permission denied.')
        return redirect('home')
    
    doc_fields = {
        'business_license': application.business_license,
        'id_document': application.id_document,
        'tax_clearance': application.tax_clearance,
        'bank_statement': application.bank_statement,
    }
    
    document = doc_fields.get(doc_type)
    if document and document.name:
        from django.http import FileResponse
        return FileResponse(document, as_attachment=True)
    
    messages.error(request, 'Document not found.')
    return redirect('suppliers:review_application_detail', application_id=application_id)