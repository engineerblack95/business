from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone

from .models import Notification, NotificationPreference
from .utils.notification_service import NotificationService


@login_required
def notification_list_view(request):
    """View all notifications"""
    
    notifications = Notification.objects.filter(user=request.user)
    
    # Filter
    notification_type = request.GET.get('type')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    is_read = request.GET.get('is_read')
    if is_read == 'unread':
        notifications = notifications.filter(is_read=False)
    elif is_read == 'read':
        notifications = notifications.filter(is_read=True)
    
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'notifications': page_obj,
        'unread_count': NotificationService.get_unread_count(request.user),
        'current_type': notification_type,
        'current_read_filter': is_read,
    }
    return render(request, 'notifications/list.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications:list')


@login_required
def mark_all_read(request):
    """Mark all notifications as read"""
    
    NotificationService.mark_all_as_read(request.user)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notifications:list')


@login_required
def delete_notification(request, notification_id):
    """Delete a notification"""
    
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    
    if request.method == 'POST':
        notification.delete()
        messages.success(request, 'Notification deleted.')
    
    return redirect('notifications:list')


@login_required
def notification_preferences_view(request):
    """Manage notification preferences"""
    
    prefs, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        prefs.email_enabled = request.POST.get('email_enabled') == 'on'
        prefs.push_enabled = request.POST.get('push_enabled') == 'on'
        prefs.sms_enabled = request.POST.get('sms_enabled') == 'on'
        
        prefs.order_notifications = request.POST.get('order_notifications') == 'on'
        prefs.payment_notifications = request.POST.get('payment_notifications') == 'on'
        prefs.product_notifications = request.POST.get('product_notifications') == 'on'
        prefs.supplier_notifications = request.POST.get('supplier_notifications') == 'on'
        prefs.commission_notifications = request.POST.get('commission_notifications') == 'on'
        prefs.promotional_notifications = request.POST.get('promotional_notifications') == 'on'
        
        prefs.save()
        messages.success(request, 'Notification preferences updated.')
        return redirect('notifications:preferences')
    
    context = {'prefs': prefs}
    return render(request, 'notifications/preferences.html', context)


@login_required
def api_notifications(request):
    """API endpoint for real-time notifications"""
    
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:10]
    
    data = {
        'count': notifications.count(),
        'notifications': [
            {
                'id': str(n.id),
                'title': n.title,
                'message': n.message[:100],
                'type': n.notification_type,
                'priority': n.priority,
                'link': n.link,
                'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for n in notifications
        ]
    }
    
    return JsonResponse(data)