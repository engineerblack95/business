from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal

from products.models import Product
from products.utils.stock_manager import StockManager
from accounts.decorators import role_required, permission_required
from accounts.models import User
from notifications.utils.notification_service import NotificationService
from .models import (
    Cart, CartItem, Order, OrderItem, 
    PaymentTransaction, CommissionEarning, WithdrawalRequest,
    Wallet, WalletTransaction  # Added wallet models
)
from .forms import (
    CheckoutForm, PaymentSimulationForm, WithdrawalRequestForm, OrderFilterForm
)
from .utils.payment_processor import PaymentProcessor
from .utils.commission_calculator import CommissionCalculator
from .utils.receipt_generator import ReceiptGenerator
from .services.wallet_service import WalletService  # Added wallet service


@login_required
def cart_count_view(request):
    """API endpoint to get cart item count for navbar badge"""
    try:
        cart, created = Cart.objects.get_or_create(customer=request.user)
        total_items = cart.get_total_items()
        return JsonResponse({'count': total_items})
    except Exception as e:
        return JsonResponse({'count': 0, 'error': str(e)})


@login_required
@role_required(['customer'])
def cart_view(request):
    """View shopping cart"""
    cart, created = Cart.objects.get_or_create(customer=request.user)
    
    context = {
        'cart': cart,
        'total_items': cart.get_total_items(),
        'subtotal_base': cart.get_total_base_price(),
        'total_vat': cart.get_total_vat(),
        'grand_total': cart.get_grand_total(),
    }
    return render(request, 'orders/cart.html', context)


@login_required
@role_required(['customer'])
def add_to_cart(request, product_id):
    """Add product to cart"""
    product = get_object_or_404(Product, id=product_id, status='approved')
    
    # Check if product is in stock
    if not product.is_in_stock():
        messages.error(request, f'{product.name} is out of stock.')
        return redirect('products:detail', slug=product.slug)
    
    quantity = int(request.POST.get('quantity', 1))
    
    # Check if requested quantity is available
    if quantity > product.exact_quantity:
        messages.error(request, f'Only {product.exact_quantity} units available.')
        return redirect('products:detail', slug=product.slug)
    
    # Get or create cart
    cart, created = Cart.objects.get_or_create(customer=request.user)
    
    # Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    messages.success(request, f'{product.name} added to cart.')
    return redirect('orders:cart')


@login_required
@role_required(['customer'])
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity <= 0:
            cart_item.delete()
            messages.success(request, 'Item removed from cart.')
        else:
            # Check stock availability
            if quantity > cart_item.product.exact_quantity:
                messages.error(request, f'Only {cart_item.product.exact_quantity} units available.')
            else:
                cart_item.quantity = quantity
                cart_item.save()
                messages.success(request, 'Cart updated.')
    
    return redirect('orders:cart')


@login_required
@role_required(['customer'])
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    cart_item.delete()
    messages.success(request, 'Item removed from cart.')
    return redirect('orders:cart')


@login_required
@role_required(['customer'])
@transaction.atomic
def checkout_view(request):
    """Checkout process"""
    cart = get_object_or_404(Cart, customer=request.user)
    
    if cart.is_empty():
        messages.error(request, 'Your cart is empty.')
        return redirect('products:list')
    
    # Check stock for all items
    for item in cart.items.all():
        if item.quantity > item.product.exact_quantity:
            messages.error(request, f'{item.product.name} has insufficient stock. Only {item.product.exact_quantity} available.')
            return redirect('orders:cart')
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Create order
            order = Order.objects.create(
                customer=request.user,
                subtotal_base=cart.get_total_base_price(),
                total_vat=cart.get_total_vat(),
                grand_total=cart.get_grand_total(),
                shipping_address=form.cleaned_data['shipping_address'],
                shipping_phone=form.cleaned_data['phone_number'],
                shipping_notes=form.cleaned_data.get('notes', ''),
                payment_method='mobile_money',
            )
            
            # Create order items from cart items
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    base_price=cart_item.snapshot_base_price,
                    vat_amount=cart_item.snapshot_vat_amount,
                    final_price=cart_item.snapshot_final_price,
                    is_supplier_product=cart_item.product.is_supplier_product,
                )
                
                # Decrease stock
                cart_item.product.decrease_stock(cart_item.quantity)
            
            # Clear cart
            cart.clear_cart()
            
            # Store order ID in session for payment
            request.session['pending_order_id'] = str(order.id)
            
            # Redirect to payment
            return redirect('orders:payment', order_id=order.id)
    else:
        form = CheckoutForm(initial={
            'phone_number': getattr(request.user, 'phone', ''),
        })
    
    context = {
        'cart': cart,
        'form': form,
        'subtotal_base': cart.get_total_base_price(),
        'total_vat': cart.get_total_vat(),
        'grand_total': cart.get_grand_total(),
        'total_items': cart.get_total_items(),
    }
    return render(request, 'orders/checkout.html', context)


@login_required
@role_required(['customer'])
@transaction.atomic
def payment_view(request, order_id):
    """Payment page for order with automatic wallet splitting"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.payment_status != 'pending':
        messages.warning(request, 'This order has already been paid.')
        return redirect('orders:order_detail', order_id=order.id)
    
    if request.method == 'POST':
        form = PaymentSimulationForm(request.POST)
        if form.is_valid():
            # Process payment (simulated for now)
            success, transaction_obj, message = PaymentProcessor.process_simulated_payment(
                order,
                form.cleaned_data['mobile_money_number']
            )
            
            if success:
                # ============================================================
                # CRITICAL: Auto-split payment into wallets
                # This distributes funds to: Admin Commission, Supplier Wallet, Tax Wallet
                # ============================================================
                try:
                    wallet_result = WalletService.process_order_split(order)
                    
                    if wallet_result['success']:
                        messages.success(request, f'{message} Funds have been automatically distributed.')
                        
                        # Send notification to admin about commission
                        admin_user = User.objects.filter(role='admin').first()
                        if admin_user:
                            NotificationService.create_notification(
                                user=admin_user,
                                title="💰 New Commission Earned!",
                                message=f"Commission earned from order #{order.order_number}. Total: {order.get_commission_total():,.0f} FRW",
                                notification_type='commission',
                                priority='medium',
                                link='/dashboard/admin/wallet/'
                            )
                        
                        # Send notification to suppliers about their earnings
                        for order_item in order.items.filter(is_supplier_product=True):
                            supplier = order_item.product.owner
                            NotificationService.create_notification(
                                user=supplier,
                                title="💵 New Earnings Received!",
                                message=f"Your product '{order_item.product.name}' was sold. {order_item.supplier_payout_amount:,.0f} FRW added to your wallet.",
                                notification_type='earnings',
                                priority='medium',
                                link='/dashboard/supplier/wallet/'
                            )
                    else:
                        messages.warning(request, f'{message} But wallet distribution encountered issues: {wallet_result.get("error", "")}')
                        
                except Exception as e:
                    print(f"Wallet split error: {e}")
                    messages.warning(request, f'{message} Please contact support if funds are not reflected.')
                
                return redirect('orders:order_confirmation', order_id=order.id)
            else:
                messages.error(request, f'Payment failed: {message}')
    else:
        form = PaymentSimulationForm()
    
    context = {
        'order': order,
        'form': form,
        'grand_total': order.grand_total,
    }
    return render(request, 'orders/payment_simulation.html', context)


@login_required
def order_confirmation_view(request, order_id):
    """Order confirmation page after successful payment"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.payment_status not in ['simulated', 'paid']:
        messages.error(request, 'Order not paid yet.')
        return redirect('orders:payment', order_id=order.id)
    
    context = {
        'order': order,
        'items': order.items.all(),
    }
    return render(request, 'orders/order_confirmation.html', context)


@login_required
def order_detail_view(request, order_id):
    """View order details - accessible by customer, supplier (if product included), and admin"""
    
    try:
        order = get_object_or_404(Order, id=order_id)
    except (ValueError, TypeError):
        messages.error(request, 'Invalid order ID format.')
        return redirect('orders:order_list')
    
    # Check permissions
    is_customer = order.customer == request.user
    is_admin = request.user.role == 'admin'
    is_supplier = request.user.role == 'supplier' and order.items.filter(
        product__owner=request.user, 
        is_supplier_product=True
    ).exists()
    
    if not (is_customer or is_admin or is_supplier):
        messages.error(request, 'You do not have permission to view this order.')
        return redirect('orders:order_list')
    
    context = {
        'order': order,
        'items': order.items.all(),
        'is_supplier_view': is_supplier,
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def order_list_view(request):
    """List user's orders - shows different orders based on role"""
    
    if request.user.role == 'admin':
        # Admin sees all orders
        orders = Order.objects.all().order_by('-created_at')
    elif request.user.role == 'supplier':
        # Supplier sees orders containing their products
        orders = Order.objects.filter(
            items__product__owner=request.user,
            items__is_supplier_product=True
        ).distinct().order_by('-created_at')
    else:
        # Customer sees only their orders
        orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    
    # Apply filters
    status = request.GET.get('status')
    if status:
        orders = orders.filter(order_status=status)
    
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
        'status_filter': status,
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def download_receipt_view(request, order_id):
    """Download order receipt as PDF"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.payment_status not in ['simulated', 'paid']:
        messages.error(request, 'Receipt not available for unpaid orders.')
        return redirect('orders:order_detail', order_id=order.id)
    
    return ReceiptGenerator.download_receipt(request, order)


@login_required
@role_required(['admin'])
def admin_orders_view(request):
    """Admin view all orders"""
    orders = Order.objects.all().order_by('-created_at')
    
    # Apply filters
    filter_form = OrderFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            orders = orders.filter(order_status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('date_from'):
            orders = orders.filter(created_at__date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            orders = orders.filter(created_at__date__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data.get('order_id'):
            orders = orders.filter(order_number__icontains=filter_form.cleaned_data['order_id'])
    
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total_orders': Order.objects.count(),
        'total_revenue': Order.objects.filter(payment_status__in=['simulated', 'paid']).aggregate(total=Sum('grand_total'))['total'] or 0,
        'pending_orders': Order.objects.filter(order_status='pending').count(),
        'completed_orders': Order.objects.filter(order_status='delivered').count(),
    }
    
    context = {
        'orders': page_obj,
        'filter_form': filter_form,
        'stats': stats,
    }
    return render(request, 'orders/admin_orders.html', context)


@login_required
@role_required(['admin'])
def update_order_status_view(request, order_id):
    """Admin update order status"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.ORDER_STATUS_CHOICES):
            order.order_status = new_status
            
            if new_status == 'delivered':
                order.delivered_at = timezone.now()
            
            order.save()
            messages.success(request, f'Order status updated to {order.get_order_status_display()}')
            
            # Notify customer about status change
            NotificationService.create_notification(
                user=order.customer,
                title=f"Order Status Update - {order.order_number}",
                message=f"Your order #{order.order_number} status has been updated to {order.get_order_status_display()}.",
                notification_type='order',
                priority='medium',
                link=f'/orders/order/{order.id}/'
            )
    
    return redirect('orders:admin_orders')


@login_required
@role_required(['supplier'])
def supplier_orders_view(request):
    """Supplier view orders containing their products"""
    from django.db.models import Sum
    
    orders = Order.objects.filter(
        items__product__owner=request.user,
        items__is_supplier_product=True
    ).distinct().order_by('-created_at')
    
    # Calculate statistics
    total_revenue = 0
    pending_count = 0
    completed_count = 0
    
    for order in orders:
        for item in order.items.filter(product__owner=request.user, is_supplier_product=True):
            total_revenue += item.get_total_final_price()
        
        if order.order_status == 'pending':
            pending_count += 1
        elif order.order_status == 'delivered':
            completed_count += 1
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
        'total_revenue': total_revenue,
        'pending_count': pending_count,
        'completed_count': completed_count,
    }
    return render(request, 'orders/supplier_orders.html', context)


@login_required
@role_required(['admin'])
def commission_dashboard_view(request):
    """Admin commission dashboard - Updated with wallet integration"""
    
    # Get commission summary from WalletService
    commission_summary = WalletService.get_admin_commission_summary(request.user)
    
    # Get recent wallet transactions (commissions)
    recent_transactions = WalletService.get_wallet_transactions(
        request.user, 
        wallet_type='admin', 
        limit=20
    )
    
    # Get withdrawal requests
    withdrawal_requests = WithdrawalRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Get tax summary
    tax_summary = WalletService.get_tax_summary()
    
    context = {
        'summary': commission_summary,
        'recent_transactions': recent_transactions,
        'withdrawal_requests': withdrawal_requests,
        'tax_summary': tax_summary,
        'section': 'commissions',
    }
    return render(request, 'orders/commission_dashboard.html', context)


@login_required
@role_required(['admin'])
def request_withdrawal_view(request):
    """Admin request commission withdrawal - Updated to use WalletService"""
    
    # Get available commission
    available = WalletService.get_available_balance(request.user, 'admin')
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        phone_number = request.POST.get('phone_number', '')
        payment_method = request.POST.get('payment_method', 'mobile_money')
        notes = request.POST.get('notes', '')
        
        # Validate amount
        if amount < WalletService.MINIMUM_WITHDRAWAL:
            messages.error(request, f'Minimum withdrawal amount is {WalletService.MINIMUM_WITHDRAWAL:,.0f} FRW')
        elif amount > available:
            messages.error(request, f'Amount exceeds available balance of {available:,.0f} FRW')
        else:
            # Create withdrawal request
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
        
        return redirect('orders:commission_dashboard')
    
    context = {
        'available_commission': available,
        'minimum_withdrawal': WalletService.MINIMUM_WITHDRAWAL,
    }
    return render(request, 'orders/request_withdrawal.html', context)


@login_required
@role_required(['admin'])
def cancel_order_view(request, order_id):
    """Admin cancel order"""
    order = get_object_or_404(Order, id=order_id)
    
    if order.cancel_order():
        messages.success(request, f'Order {order.order_number} has been cancelled.')
        
        # Notify customer about cancellation
        NotificationService.create_notification(
            user=order.customer,
            title=f"Order Cancelled - {order.order_number}",
            message=f"Your order #{order.order_number} has been cancelled. Any charges will be refunded.",
            notification_type='order',
            priority='high',
            link=f'/orders/order/{order.id}/'
        )
    else:
        messages.error(request, 'Order cannot be cancelled at this stage.')
    
    return redirect('orders:admin_orders')


# ============================================================
# NEW: WALLET DASHBOARD VIEWS
# ============================================================

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
        amount = Decimal(request.POST.get('amount', 0))
        phone_number = request.POST.get('phone_number', '')
        payment_method = request.POST.get('payment_method', 'mobile_money')
        notes = request.POST.get('notes', '')
        
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
    
    # Redirect based on user role
    if request.user.role == 'admin':
        return redirect('dashboard:admin_wallet')
    else:
        return redirect('dashboard:supplier_wallet')