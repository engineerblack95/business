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
from .forms import NotificationFilterForm, ProductQuickEditForm

from products.models import Product, Category
from orders.models import Order, OrderItem, CommissionEarning, WithdrawalRequest, Wallet, WalletTransaction
from accounts.models import User
from team.models import TeamMember, TeamTask

# Import wallet service
from orders.services.wallet_service import WalletService


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
    """Admin main dashboard with wallet integration"""
    
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
        user=request.user
    ).order_by('-created_at')[:5]
    
    # Get team statistics
    team_stats = {
        'total_team_members': User.objects.filter(role='team_member').count(),
        'active_tasks': TeamTask.objects.filter(status__in=['pending', 'in_progress']).count(),
        'completed_tasks_this_month': TeamTask.objects.filter(
            status='completed',
            completed_at__month=timezone.now().month
        ).count(),
    }
    
    # Get wallet summary for admin
    wallet_summary = WalletService.get_admin_commission_summary(request.user)
    tax_summary = WalletService.get_tax_summary()
    
    context = {
        'analytics': analytics,
        'unread_notifications': unread_notifications,
        'recent_suppliers': recent_applications,
        'recent_withdrawals': recent_withdrawals,
        'team_stats': team_stats,
        'wallet_summary': wallet_summary,
        'tax_summary': tax_summary,
        'section': 'overview',
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def supplier_dashboard_view(request):
    """Supplier main dashboard with wallet integration"""
    
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
    
    # Get wallet summary for supplier
    wallet_summary = WalletService.get_supplier_earnings_summary(request.user)
    
    context = {
        'analytics': analytics,
        'unread_notifications': unread_notifications,
        'recent_products': recent_products,
        'recent_orders': recent_orders,
        'wallet_summary': wallet_summary,
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
        
        # Get tasks assigned to this team member
        assigned_tasks = TeamTask.objects.filter(
            assigned_to=request.user,
            status__in=['pending', 'in_progress']
        ).order_by('-priority', 'due_date')[:10]
        
        # Get task statistics
        task_stats = {
            'pending': TeamTask.objects.filter(assigned_to=request.user, status='pending').count(),
            'in_progress': TeamTask.objects.filter(assigned_to=request.user, status='in_progress').count(),
            'completed': TeamTask.objects.filter(assigned_to=request.user, status='completed').count(),
            'overdue': TeamTask.objects.filter(
                assigned_to=request.user,
                status__in=['pending', 'in_progress'],
                due_date__lt=timezone.now()
            ).count(),
        }
        
        # Show only allowed sections
        context = {
            'permissions': permissions,
            'assigned_tasks': assigned_tasks,
            'task_stats': task_stats,
            'section': 'overview',
        }
        
        # Load data based on permissions
        if permissions.get('can_view_orders'):
            context['recent_orders'] = Order.objects.select_related('customer').order_by('-created_at')[:10]
        
        if permissions.get('can_view_products'):
            context['recent_products'] = Product.objects.select_related('category', 'owner').order_by('-created_at')[:10]
        
        return render(request, 'dashboard/team_dashboard.html', context)
    
    # Admin fallback
    return redirect('dashboard:admin')


# ==================== TEAM MANAGEMENT VIEWS ====================

@login_required
@role_required(['admin'])
def manage_team_members_view(request):
    """Admin manage team members - Professional version"""
    
    # Get all team members (users with team_member role)
    team_members = User.objects.filter(role='team_member').select_related('team_display').order_by('-date_joined')
    
    # Get total registered customers (for reference)
    total_customers = User.objects.filter(role='customer').count()
    
    # Get count of team members with permissions
    team_members_with_perms = 0
    for member in team_members:
        if member.team_permissions and any(member.team_permissions.values()):
            team_members_with_perms += 1
    
    if request.method == 'POST':
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        position = request.POST.get('position')
        custom_position = request.POST.get('custom_position', '')
        bio = request.POST.get('bio', '')
        expertise = request.POST.get('expertise', '')
        achievements = request.POST.get('achievements', '')
        linkedin = request.POST.get('linkedin', '')
        twitter = request.POST.get('twitter', '')
        facebook = request.POST.get('facebook', '')
        instagram = request.POST.get('instagram', '')
        
        # Validate email exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(
                request, 
                f'❌ User with email "{email}" does not exist in the system.\n\n'
                f'To add this person as a team member, they must FIRST register as a customer.'
            )
            return redirect('dashboard:manage_team')
        
        # Check if user is already admin
        if user.role == 'admin':
            messages.error(request, f'❌ User "{email}" is an ADMIN and cannot be added as team member.')
            return redirect('dashboard:manage_team')
        
        # Check if user is already supplier
        if user.role == 'supplier':
            messages.error(request, f'❌ User "{email}" is a SUPPLIER. Cannot convert to team member.')
            return redirect('dashboard:manage_team')
        
        # Check if user is already team member
        if user.role == 'team_member':
            messages.warning(request, f'⚠️ User "{email}" is already a team member.')
            return redirect('dashboard:manage_team')
        
        # Update user role and permissions
        user.role = 'team_member'
        user.full_name = full_name or user.full_name
        user.phone = phone or user.phone
        
        # Set permissions from form
        user.team_permissions = {
            'can_view_orders': request.POST.get('can_view_orders') == 'on',
            'can_view_products': request.POST.get('can_view_products') == 'on',
            'can_edit_products': request.POST.get('can_edit_products') == 'on',
            'can_approve_products': request.POST.get('can_approve_products') == 'on',
            'can_manage_suppliers': request.POST.get('can_manage_suppliers') == 'on',
            'can_view_financial': request.POST.get('can_view_financial') == 'on',
            'can_view_logs': request.POST.get('can_view_logs') == 'on',
        }
        user.save()
        
        # Handle profile image if uploaded
        profile_image = None
        if request.FILES.get('profile_image'):
            profile_image = request.FILES['profile_image']
        
        # Create or update TeamMember record for About page
        team_member_record, created = TeamMember.objects.get_or_create(
            user=user,
            defaults={
                'full_name': full_name or user.full_name,
                'email': user.email,
                'phone': phone or user.phone,
                'position': position if position and position != 'other' else 'other',
                'custom_position': custom_position if position == 'other' else '',
                'bio': bio,
                'expertise': expertise,
                'achievements': achievements,
                'linkedin': linkedin,
                'twitter': twitter,
                'facebook': facebook,
                'instagram': instagram,
                'is_active': True,
            }
        )
        
        if not created:
            team_member_record.full_name = full_name or user.full_name
            team_member_record.phone = phone or user.phone
            team_member_record.bio = bio
            team_member_record.expertise = expertise
            team_member_record.achievements = achievements
            team_member_record.linkedin = linkedin
            team_member_record.twitter = twitter
            team_member_record.facebook = facebook
            team_member_record.instagram = instagram
            if position:
                if position == 'other':
                    team_member_record.position = 'other'
                    team_member_record.custom_position = custom_position
                else:
                    team_member_record.position = position
            if profile_image:
                team_member_record.profile_image = profile_image
            team_member_record.save()
        elif profile_image:
            team_member_record.profile_image = profile_image
            team_member_record.save()
        
        # Send notification
        try:
            NotificationManager.send_notification(
                user=user,
                title="Welcome to the Team! 🎉",
                message=f"You have been added as a team member at HerosTechnology. "
                        f"You can now access the team dashboard.",
                notification_type='system',
                priority='high',
                link='/dashboard/team/'
            )
        except Exception as e:
            print(f"Notification error: {e}")
        
        perm_count = sum(1 for v in user.team_permissions.values() if v)
        messages.success(
            request, 
            f'✅ Team member "{user.email}" added successfully!\n'
            f'User role updated to Team Member with {perm_count} permissions.'
        )
        return redirect('dashboard:manage_team')
    
    context = {
        'team_members': team_members,
        'total_customers': total_customers,
        'team_members_with_perms': team_members_with_perms,
        'section': 'team',
    }
    return render(request, 'dashboard/manage_team.html', context)


@login_required
@role_required(['admin'])
def edit_team_member_view(request, user_id):
    """Admin edit team member permissions and details"""
    
    team_member = get_object_or_404(User, id=user_id)
    
    # Only allow editing team members or customers (to promote)
    if team_member.role not in ['team_member', 'customer']:
        messages.error(request, f'Cannot edit user with role: {team_member.get_role_display()}')
        return redirect('dashboard:manage_team')
    
    # Get associated TeamMember record if exists
    team_record = TeamMember.objects.filter(user=team_member).first()
    
    if request.method == 'POST':
        action = request.POST.get('action', 'update')
        
        if action == 'update':
            # Update basic info
            team_member.full_name = request.POST.get('full_name', team_member.full_name)
            team_member.phone = request.POST.get('phone', team_member.phone)
            
            # Update permissions
            team_member.team_permissions = {
                'can_view_orders': request.POST.get('can_view_orders') == 'on',
                'can_view_products': request.POST.get('can_view_products') == 'on',
                'can_edit_products': request.POST.get('can_edit_products') == 'on',
                'can_approve_products': request.POST.get('can_approve_products') == 'on',
                'can_manage_suppliers': request.POST.get('can_manage_suppliers') == 'on',
                'can_view_financial': request.POST.get('can_view_financial') == 'on',
                'can_view_logs': request.POST.get('can_view_logs') == 'on',
            }
            
            # Update role if promoting from customer
            if team_member.role == 'customer':
                team_member.role = 'team_member'
                promotion_message = " User has been promoted to Team Member."
            else:
                promotion_message = ""
            
            team_member.save()
            
            # Update or create TeamMember record
            position = request.POST.get('position')
            bio = request.POST.get('bio', '')
            expertise = request.POST.get('expertise', '')
            achievements = request.POST.get('achievements', '')
            linkedin = request.POST.get('linkedin', '')
            twitter = request.POST.get('twitter', '')
            facebook = request.POST.get('facebook', '')
            instagram = request.POST.get('instagram', '')
            
            if team_record:
                team_record.full_name = team_member.full_name
                team_record.phone = team_member.phone
                team_record.bio = bio
                team_record.expertise = expertise
                team_record.achievements = achievements
                team_record.linkedin = linkedin
                team_record.twitter = twitter
                team_record.facebook = facebook
                team_record.instagram = instagram
                if position:
                    if position == 'other':
                        team_record.position = 'other'
                        team_record.custom_position = request.POST.get('custom_position', '')
                    else:
                        team_record.position = position
                team_record.save()
            elif team_member.role == 'team_member':
                # Create new TeamMember record if it doesn't exist
                TeamMember.objects.create(
                    user=team_member,
                    full_name=team_member.full_name,
                    email=team_member.email,
                    phone=team_member.phone,
                    position=position if position and position != 'other' else 'other',
                    custom_position=request.POST.get('custom_position', '') if position == 'other' else '',
                    bio=bio,
                    expertise=expertise,
                    achievements=achievements,
                    linkedin=linkedin,
                    twitter=twitter,
                    facebook=facebook,
                    instagram=instagram,
                    is_active=True,
                )
            
            # Handle profile image update
            if request.FILES.get('profile_image'):
                if team_record:
                    team_record.profile_image = request.FILES['profile_image']
                    team_record.save()
            
            perm_count = sum(1 for v in team_member.team_permissions.values() if v)
            messages.success(
                request, 
                f'✅ Team member "{team_member.email}" updated successfully!{promotion_message}\n'
                f'Current permissions: {perm_count}'
            )
            
        elif action == 'remove':
            # Remove team member (revert to customer)
            team_member.role = 'customer'
            team_member.team_permissions = {}
            team_member.save()
            
            # Optionally deactivate TeamMember record
            if team_record:
                team_record.is_active = False
                team_record.save()
            
            messages.info(request, f'⚠️ Team member "{team_member.email}" removed. Role reverted to Customer.')
        
        return redirect('dashboard:manage_team')
    
    # Get current permissions for checkboxes
    current_perms = team_member.team_permissions
    
    context = {
        'team_member': team_member,
        'team_record': team_record,
        'current_perms': current_perms,
        'section': 'team',
    }
    return render(request, 'dashboard/edit_team_member.html', context)


@login_required
@role_required(['admin'])
def remove_team_member_view(request, user_id):
    """Admin remove team member - API endpoint for AJAX/Form submission"""
    
    team_member = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        email = team_member.email
        
        # Revert to customer
        team_member.role = 'customer'
        team_member.team_permissions = {}
        team_member.save()
        
        # Deactivate TeamMember record
        team_record = TeamMember.objects.filter(user=team_member).first()
        if team_record:
            team_record.is_active = False
            team_record.save()
        
        # Send notification about removal
        try:
            NotificationManager.send_notification(
                user=team_member,
                title="Team Member Access Removed",
                message=f"Your team member access has been removed. "
                        f"You now have customer access only.",
                notification_type='system',
                priority='medium',
                link='/dashboard/customer/'
            )
        except Exception as e:
            print(f"Notification error: {e}")
        
        messages.success(request, f'✅ Team member "{email}" removed successfully. User role reverted to Customer.')
    
    return redirect('dashboard:manage_team')


@login_required
@role_required(['admin'])
def get_team_member_details_api(request, user_id):
    """API endpoint to get team member details for editing"""
    
    team_member = get_object_or_404(User, id=user_id)
    
    if team_member.role not in ['team_member', 'customer']:
        return JsonResponse({'error': 'Invalid user type'}, status=400)
    
    team_record = TeamMember.objects.filter(user=team_member).first()
    
    data = {
        'id': str(team_member.id),
        'email': team_member.email,
        'full_name': team_member.full_name or '',
        'phone': team_member.phone or '',
        'role': team_member.role,
        'permissions': team_member.team_permissions,
        'position': team_record.position if team_record else '',
        'custom_position': team_record.custom_position if team_record else '',
        'bio': team_record.bio if team_record else '',
        'expertise': team_record.expertise if team_record else '',
        'achievements': team_record.achievements if team_record else '',
        'linkedin': team_record.linkedin if team_record else '',
        'twitter': team_record.twitter if team_record else '',
        'facebook': team_record.facebook if team_record else '',
        'instagram': team_record.instagram if team_record else '',
        'display_order': team_record.display_order if team_record else 0,
        'is_active': team_record.is_active if team_record else True,
        'featured': team_record.featured if team_record else False,
    }
    
    return JsonResponse(data)


# ==================== WALLET & EARNINGS VIEWS (NEW) ====================

@login_required
def supplier_wallet_view(request):
    """Supplier view their wallet balance and transactions"""
    
    if request.user.role != 'supplier':
        messages.error(request, 'Access denied. Supplier only.')
        return redirect('dashboard:home')
    
    # Get wallet balance
    wallet_info = WalletService.get_wallet_balance(request.user, 'supplier')
    
    # Get recent transactions
    transactions = WalletService.get_wallet_transactions(
        request.user, 
        wallet_type='supplier', 
        limit=30
    )
    
    # Get withdrawal requests
    withdrawals = WithdrawalRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]
    
    # Get earnings summary
    earnings_summary = WalletService.get_supplier_earnings_summary(request.user)
    
    context = {
        'wallet': wallet_info,
        'transactions': transactions,
        'withdrawals': withdrawals,
        'earnings_summary': earnings_summary,
        'minimum_withdrawal': WalletService.MINIMUM_WITHDRAWAL,
        'section': 'wallet',
    }
    return render(request, 'dashboard/supplier_wallet.html', context)


@login_required
def supplier_earnings_view(request):
    """Supplier earnings analytics and reports"""
    
    if request.user.role != 'supplier':
        messages.error(request, 'Access denied. Supplier only.')
        return redirect('dashboard:home')
    
    # Get earnings summary
    earnings_summary = WalletService.get_supplier_earnings_summary(request.user)
    
    # Get all completed payouts (orders delivered)
    from orders.models import OrderItem
    completed_orders = OrderItem.objects.filter(
        product__owner=request.user,
        is_supplier_product=True,
        order__order_status='delivered'
    ).select_related('order', 'product').order_by('-created_at')
    
    # Calculate monthly earnings
    monthly_earnings = completed_orders.filter(
        created_at__year=timezone.now().year
    ).values('created_at__month').annotate(
        total=Sum('supplier_payout_amount'),
        count=Count('id')
    ).order_by('-created_at__month')
    
    # Get top products by earnings
    top_products = completed_orders.values(
        'product__name',
        'product__id'
    ).annotate(
        total_earned=Sum('supplier_payout_amount'),
        quantity_sold=Sum('quantity')
    ).order_by('-total_earned')[:10]
    
    context = {
        'earnings_summary': earnings_summary,
        'completed_orders': completed_orders[:50],
        'monthly_earnings': monthly_earnings,
        'top_products': top_products,
        'section': 'earnings',
    }
    return render(request, 'dashboard/supplier_earnings.html', context)


@login_required
@role_required(['admin'])
def admin_wallet_view(request):
    """Admin view their commission wallet"""
    
    # Get wallet balance
    wallet_info = WalletService.get_wallet_balance(request.user, 'admin')
    
    # Get recent transactions
    transactions = WalletService.get_wallet_transactions(
        request.user, 
        wallet_type='admin', 
        limit=30
    )
    
    # Get withdrawal requests
    withdrawals = WithdrawalRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]
    
    # Get commission summary
    commission_summary = WalletService.get_admin_commission_summary(request.user)
    
    # Get tax summary
    tax_summary = WalletService.get_tax_summary()
    
    context = {
        'wallet': wallet_info,
        'transactions': transactions,
        'withdrawals': withdrawals,
        'commission_summary': commission_summary,
        'tax_summary': tax_summary,
        'minimum_withdrawal': WalletService.MINIMUM_WITHDRAWAL,
        'section': 'wallet',
    }
    return render(request, 'dashboard/admin_wallet.html', context)


@login_required
@role_required(['admin'])
def admin_commission_view(request):
    """Admin commission analytics and reports"""
    
    # Get commission summary
    commission_summary = WalletService.get_admin_commission_summary(request.user)
    
    # Get all commission transactions
    admin_wallet = Wallet.objects.filter(user=request.user, wallet_type='admin').first()
    
    commission_transactions = []
    if admin_wallet:
        commission_transactions = WalletTransaction.objects.filter(
            wallet=admin_wallet,
            category='commission',
            transaction_type='credit'
        ).select_related('order').order_by('-created_at')[:100]
    
    # Calculate monthly commission
    monthly_commission = []
    if admin_wallet:
        monthly_commission = WalletTransaction.objects.filter(
            wallet=admin_wallet,
            category='commission',
            transaction_type='credit',
            created_at__year=timezone.now().year
        ).values('created_at__month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-created_at__month')
    
    # Get top suppliers by commission paid
    top_suppliers = WalletTransaction.objects.filter(
        wallet=admin_wallet,
        category='commission',
        transaction_type='credit'
    ).values('order_item__product__owner__email').annotate(
        total_commission=Sum('amount'),
        product_count=Count('order_item__product', distinct=True)
    ).order_by('-total_commission')[:10]
    
    # Get tax summary
    tax_summary = WalletService.get_tax_summary()
    
    context = {
        'commission_summary': commission_summary,
        'commission_transactions': commission_transactions,
        'monthly_commission': monthly_commission,
        'top_suppliers': top_suppliers,
        'tax_summary': tax_summary,
        'section': 'commission',
    }
    return render(request, 'dashboard/admin_commission.html', context)


@login_required
def request_wallet_withdrawal_view(request):
    """User request withdrawal from their wallet"""
    
    # Determine wallet type based on role
    if request.user.role == 'supplier':
        wallet_type = 'supplier'
        redirect_url = 'dashboard:supplier_wallet'
    elif request.user.role == 'admin':
        wallet_type = 'admin'
        redirect_url = 'dashboard:admin_wallet'
    else:
        messages.error(request, 'Only suppliers and admins can request withdrawals.')
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        phone_number = request.POST.get('phone_number', '')
        payment_method = request.POST.get('payment_method', 'mobile_money')
        notes = request.POST.get('notes', '')
        
        try:
            amount = Decimal(amount)
        except:
            messages.error(request, 'Invalid amount.')
            return redirect(redirect_url)
        
        result = WalletService.create_withdrawal_request(
            user=request.user,
            amount=amount,
            phone_number=phone_number,
            payment_method=payment_method,
            notes=notes
        )
        
        if result['success']:
            messages.success(request, f'Withdrawal request of {amount:,.0f} FRW submitted successfully.')
        else:
            messages.error(request, result['error'])
    
    return redirect(redirect_url)


@login_required
@role_required(['admin'])
def process_withdrawal_request_view(request, withdrawal_id):
    """Admin process a withdrawal request (approve/reject)"""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            result = WalletService.process_withdrawal(
                withdrawal_id=withdrawal_id,
                admin_user=request.user,
                approve=True
            )
        else:
            reason = request.POST.get('rejection_reason', 'Not specified')
            result = WalletService.process_withdrawal(
                withdrawal_id=withdrawal_id,
                admin_user=request.user,
                approve=False,
                rejection_reason=reason
            )
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result.get('error', 'Failed to process withdrawal'))
    
    return redirect('dashboard:admin_wallet')


# ==================== NOTIFICATION VIEWS ====================

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


# ==================== PRODUCT MANAGEMENT VIEWS ====================

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


# ==================== SUPPLIER MANAGEMENT VIEWS ====================

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
        if application.tax_id:
            supplier.tax_id = application.tax_id
        supplier.save()
        
        # Update application status
        application.status = 'approved'
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.approved_at = timezone.now()
        application.save()
        
        # Create or update supplier profile
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


# ==================== ACTIVITY LOGS VIEW ====================

@login_required
@role_required(['admin'])
def activity_logs_view(request):
    """View system activity logs - shows login history with device, OS, browser, location"""
    
    from accounts.models import UserLoginHistory
    
    # Get all login history with user details
    logs = UserLoginHistory.objects.select_related('user').order_by('-login_time')
    
    # Apply filters
    user_id = request.GET.get('user')
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    # Device filter
    device_type = request.GET.get('device')
    if device_type:
        logs = logs.filter(device_type=device_type)
    
    # Optional: OS Type filter
    os_type = request.GET.get('os_type')
    if os_type:
        logs = logs.filter(os_type=os_type)
    
    # Optional: Browser filter
    browser = request.GET.get('browser')
    if browser:
        logs = logs.filter(browser__icontains=browser)
    
    # Date range filter
    date_from = request.GET.get('date_from')
    if date_from:
        from datetime import datetime
        logs = logs.filter(login_time__date__gte=datetime.strptime(date_from, '%Y-%m-%d'))
    
    date_to = request.GET.get('date_to')
    if date_to:
        from datetime import datetime
        logs = logs.filter(login_time__date__lte=datetime.strptime(date_to, '%Y-%m-%d'))
    
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get users for filter dropdown
    users = User.objects.all().order_by('email')
    
    # Device choices for filter dropdown
    device_choices = [
        ('', 'All Devices'),
        ('pc', '💻 PC/Laptop'),
        ('smartphone', '📱 Smartphone'),
        ('tablet', '📟 Tablet'),
        ('bot', '🤖 Bot/Crawler'),
        ('unknown', '❓ Unknown'),
    ]
    
    # OS choices for filter dropdown
    os_choices = [
        ('', 'All OS'),
        ('windows', '🪟 Windows'),
        ('macos', '🍎 macOS'),
        ('linux', '🐧 Linux'),
        ('android', '📱 Android'),
        ('ios', '📱 iOS'),
        ('chromeos', '🌐 Chrome OS'),
        ('unknown', '❓ Unknown'),
    ]
    
    context = {
        'logs': page_obj,
        'users': users,
        'device_choices': device_choices,
        'os_choices': os_choices,
        'selected_device': request.GET.get('device', ''),
        'selected_os': request.GET.get('os_type', ''),
        'selected_browser': request.GET.get('browser', ''),
        'selected_user': user_id,
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
        'section': 'logs',
    }
    return render(request, 'dashboard/activity_logs.html', context)


# ==================== REPORTS VIEW ====================

@login_required
@role_required(['admin'])
def reports_view(request):
    """Generate and view reports"""
    
    from datetime import timedelta, datetime
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
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() - timedelta(days=30)
            end_date = timezone.now().date()
    
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