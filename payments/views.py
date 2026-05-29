from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal

from accounts.decorators import role_required, permission_required
from orders.models import Order
from .models import PaymentTransaction, WithdrawalRequest, SupplierPayout, PaymentMethod
from .forms import MobileMoneyPaymentForm, WithdrawalRequestForm, PaymentFilterForm, SupplierPayoutFilterForm
from .services.payment_gateway import PaymentGateway
from .utils.commission_handler import CommissionHandler, SupplierPayoutHandler


@login_required
def payment_methods_view(request):
    """View available payment methods"""
    
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    
    context = {
        'payment_methods': payment_methods,
    }
    return render(request, 'payments/payment_methods.html', context)


@login_required
def initiate_payment_view(request, order_id):
    """Initiate payment for an order"""
    
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # Check if already paid
    if order.payment_status in ['simulated', 'paid']:
        messages.warning(request, 'This order has already been paid.')
        return redirect('orders:order_detail', order_id=order.id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        if payment_method == 'mobile_money_mtn':
            form = MobileMoneyPaymentForm(request.POST)
            if form.is_valid():
                mobile_number = form.cleaned_data['mobile_money_number']
                provider = form.cleaned_data['provider']
                
                # Initiate payment
                transaction, success, message = PaymentGateway.initiate_payment(
                    order=order,
                    payment_method=f'mobile_money_{provider}',
                    mobile_money_number=mobile_number,
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                if success:
                    messages.success(request, message)
                    return redirect('payments:payment_status', transaction_id=transaction.transaction_id)
                else:
                    messages.error(request, message)
        
        elif payment_method == 'simulated':
            # Simulated payment for development
            transaction, success, message = PaymentGateway.initiate_payment(
                order=order,
                payment_method='simulated',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            if success:
                messages.success(request, 'Payment successful!')
                return redirect('payments:payment_success', transaction_id=transaction.transaction_id)
            else:
                messages.error(request, message)
    
    else:
        form = MobileMoneyPaymentForm()
    
    context = {
        'order': order,
        'form': form,
        'grand_total': order.grand_total,
    }
    return render(request, 'payments/payment_form.html', context)


@login_required
def payment_status_view(request, transaction_id):
    """View payment status"""
    
    transaction = get_object_or_404(PaymentTransaction, transaction_id=transaction_id, customer=request.user)
    
    context = {
        'transaction': transaction,
    }
    return render(request, 'payments/payment_confirmation.html', context)


@login_required
def payment_success_view(request, transaction_id):
    """Payment success page"""
    
    transaction = get_object_or_404(PaymentTransaction, transaction_id=transaction_id, customer=request.user)
    
    context = {
        'transaction': transaction,
        'order': transaction.order,
    }
    return render(request, 'payments/payment_success.html', context)


@login_required
def payment_history_view(request):
    """View payment history"""
    
    transactions = PaymentTransaction.objects.filter(
        customer=request.user
    ).select_related('order').order_by('-initiated_at')
    
    # Apply filters
    filter_form = PaymentFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            transactions = transactions.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('payment_method'):
            transactions = transactions.filter(payment_method=filter_form.cleaned_data['payment_method'])
    
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'transactions': page_obj,
        'filter_form': filter_form,
    }
    return render(request, 'payments/payment_history.html', context)


@login_required
@role_required(['admin'])
def commission_dashboard_view(request):
    """Admin commission dashboard"""
    
    commission_summary = CommissionHandler.get_admin_commission_summary(request.user)
    
    # Get recent commissions
    recent_commissions = CommissionRecord.objects.filter(
        admin=request.user
    ).select_related('order_item__product', 'order_item__order')[:20]
    
    # Get withdrawal requests
    withdrawal_requests = WithdrawalRequest.objects.filter(
        admin=request.user
    ).order_by('-created_at')
    
    # Process withdrawal request
    if request.method == 'POST' and 'withdraw' in request.POST:
        form = WithdrawalRequestForm(request.POST, available_commission=commission_summary['available'])
        if form.is_valid():
            withdrawal = form.save(commit=False)
            withdrawal.admin = request.user
            withdrawal.save()
            messages.success(request, f'Withdrawal request of {withdrawal.amount} FRW submitted.')
            return redirect('payments:commission_dashboard')
    else:
        form = WithdrawalRequestForm(available_commission=commission_summary['available'])
    
    context = {
        'summary': commission_summary,
        'recent_commissions': recent_commissions,
        'withdrawal_requests': withdrawal_requests,
        'form': form,
    }
    return render(request, 'payments/commission_dashboard.html', context)


@login_required
@role_required(['admin'])
def withdrawal_history_view(request):
    """View withdrawal history"""
    
    withdrawals = WithdrawalRequest.objects.filter(
        admin=request.user
    ).order_by('-created_at')
    
    paginator = Paginator(withdrawals, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'withdrawals': page_obj,
    }
    return render(request, 'payments/withdrawal_history.html', context)


@login_required
@role_required(['admin'])
def process_withdrawal_view(request, withdrawal_id):
    """Process withdrawal request (Admin action)"""
    
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            withdrawal.approve(request.user)
            
            # Process the withdrawal (mark commissions as withdrawn)
            CommissionHandler.process_withdrawal(withdrawal)
            
            messages.success(request, f'Withdrawal request approved. Amount: {withdrawal.amount} FRW')
        
        elif action == 'reject':
            reason = request.POST.get('reason', 'Not specified')
            withdrawal.reject(request.user, reason)
            messages.warning(request, f'Withdrawal request rejected: {reason}')
        
        elif action == 'complete':
            reference = request.POST.get('reference', '')
            withdrawal.mark_completed(reference)
            messages.success(request, 'Withdrawal marked as completed.')
        
        return redirect('payments:commission_dashboard')
    
    context = {
        'withdrawal': withdrawal,
    }
    return render(request, 'payments/process_withdrawal.html', context)


@login_required
@role_required(['admin'])
def supplier_payouts_view(request):
    """Admin view and manage supplier payouts"""
    
    payouts = SupplierPayout.objects.select_related('supplier').order_by('-created_at')
    
    # Apply filters
    filter_form = SupplierPayoutFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            payouts = payouts.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('supplier'):
            payouts = payouts.filter(supplier__email__icontains=filter_form.cleaned_data['supplier'])
    
    paginator = Paginator(payouts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total_pending': payouts.filter(status='pending').aggregate(total=models.Sum('net_amount'))['total'] or 0,
        'total_processing': payouts.filter(status='processing').aggregate(total=models.Sum('net_amount'))['total'] or 0,
        'total_completed': payouts.filter(status='completed').aggregate(total=models.Sum('net_amount'))['total'] or 0,
        'total_commission': payouts.aggregate(total=models.Sum('commission_deducted'))['total'] or 0,
    }
    
    context = {
        'payouts': page_obj,
        'filter_form': filter_form,
        'stats': stats,
    }
    return render(request, 'payments/supplier_payouts.html', context)


@login_required
@role_required(['supplier'])
def my_payouts_view(request):
    """Supplier view their payouts"""
    
    payouts = SupplierPayout.objects.filter(
        supplier=request.user
    ).order_by('-created_at')
    
    # Statistics
    stats = {
        'pending': payouts.filter(status='pending').aggregate(total=models.Sum('net_amount'))['total'] or 0,
        'processing': payouts.filter(status='processing').aggregate(total=models.Sum('net_amount'))['total'] or 0,
        'completed': payouts.filter(status='completed').aggregate(total=models.Sum('net_amount'))['total'] or 0,
        'total': payouts.filter(status='completed').aggregate(total=models.Sum('net_amount'))['total'] or 0,
    }
    
    context = {
        'payouts': payouts,
        'stats': stats,
    }
    return render(request, 'payments/my_payouts.html', context)


@login_required
def transaction_detail_view(request, transaction_id):
    """View transaction details"""
    
    transaction = get_object_or_404(
        PaymentTransaction,
        transaction_id=transaction_id
    )
    
    # Check permission
    if request.user.role not in ['admin'] and transaction.customer != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('payments:payment_history')
    
    context = {
        'transaction': transaction,
    }
    return render(request, 'payments/transaction_details.html', context)


@csrf_exempt
@require_http_methods(['POST'])
def payment_webhook_view(request, provider):
    """Webhook endpoint for payment providers"""
    
    import json
    from .models import PaymentWebhookLog
    
    # Log webhook
    log = PaymentWebhookLog.objects.create(
        provider=provider,
        event_type=request.GET.get('event', 'unknown'),
        payload=json.loads(request.body) if request.body else {},
        headers=dict(request.headers)
    )
    
    # Process based on provider
    if provider == 'mtn':
        # Process MTN webhook
        payload = log.payload
        transaction_id = payload.get('transaction_id')
        
        if transaction_id:
            try:
                transaction = PaymentTransaction.objects.get(provider_transaction_id=transaction_id)
                transaction.mark_completed()
                log.processed = True
                log.transaction = transaction
                log.save()
                
                return JsonResponse({'status': 'ok'})
            except PaymentTransaction.DoesNotExist:
                pass
    
    log.save()
    return JsonResponse({'status': 'received'})