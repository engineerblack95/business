from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse

from accounts.decorators import role_required, permission_required
from .models import TeamMember, TeamTask, TeamActivity
from .forms import TeamMemberForm, TeamTaskForm, TaskStatusForm
from dashboard.utils.notifications import NotificationManager
from accounts.models import User


def about_view(request):
    """Public about page showing team members"""
    
    # Get all active team members, ordered by display_order
    team_members = TeamMember.objects.filter(is_active=True).order_by('display_order')
    
    # Get leadership team (featured members)
    leadership = team_members.filter(featured=True)
    
    # Get other team members (non-featured)
    other_members = team_members.filter(featured=False)
    
    context = {
        'leadership': leadership,
        'team_members': other_members,
        'total_members': team_members.count(),
    }
    return render(request, 'about.html', context)


# ==================== TEAM DASHBOARD VIEW ====================

@login_required
@role_required(['admin', 'team_member'])
def team_dashboard_view(request):
    """Team member dashboard - shows tasks and permissions based on user role"""
    
    # Get user's permissions
    permissions = {}
    if hasattr(request.user, 'team_permissions'):
        permissions = request.user.team_permissions
    elif request.user.role == 'admin':
        # Admin has all permissions
        permissions = {
            'can_view_orders': True,
            'can_view_products': True,
            'can_edit_products': True,
            'can_approve_products': True,
            'can_manage_suppliers': True,
            'can_view_logs': True,
            'can_view_financial': True,
        }
    
    # Get tasks assigned to this user
    tasks = TeamTask.objects.filter(assigned_to=request.user)
    
    # Task statistics
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    task_stats = {
        'pending': tasks.filter(status='pending').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'review': tasks.filter(status='review').count(),
        'completed': completed_tasks,
        'cancelled': tasks.filter(status='cancelled').count(),
        'overdue': tasks.filter(status__in=['pending', 'in_progress', 'review'], due_date__lt=timezone.now()).count(),
        'total_tasks': total_tasks,
        'completion_percentage': round(completion_percentage, 1),
    }
    
    # Get recent tasks (last 5)
    recent_tasks = tasks.order_by('-priority', 'due_date')[:5]
    
    # Get recent orders if permission exists
    recent_orders = []
    if permissions.get('can_view_orders', False) or request.user.role == 'admin':
        from orders.models import Order
        recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:5]
    
    # Get recent products if permission exists
    recent_products = []
    if permissions.get('can_view_products', False) or request.user.role == 'admin':
        from products.models import Product
        recent_products = Product.objects.select_related('category', 'owner').order_by('-created_at')[:5]
    
    context = {
        'permissions': permissions,
        'task_stats': task_stats,
        'recent_tasks': recent_tasks,
        'recent_orders': recent_orders,
        'recent_products': recent_products,
        'section': 'overview',
    }
    return render(request, 'team/dashboard.html', context)


# ==================== ADMIN TEAM MANAGEMENT ====================

@login_required
@role_required(['admin'])
def manage_team_view(request):
    """Admin manage team members - User must already be registered"""
    
    if request.method == 'POST':
        form = TeamMemberForm(request.POST, request.FILES)
        if form.is_valid():
            team_member = form.save()
            
            # Success message with user info
            user = team_member.user
            messages.success(
                request, 
                f'Team member {team_member.full_name} added successfully! '
                f'User {user.email} now has team_member role with {len(user.team_permissions)} permissions.'
            )
            return redirect('team:manage_team')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    if field == 'user_email':
                        messages.error(request, f'❌ {error}')
                    else:
                        messages.error(request, f'{field}: {error}')
    else:
        form = TeamMemberForm()
    
    team_members = TeamMember.objects.select_related('user').all().order_by('display_order')
    
    # Get all registered users (for reference)
    registered_users = User.objects.filter(role__in=['customer', 'supplier']).count()
    
    context = {
        'form': form,
        'team_members': team_members,
        'registered_users': registered_users,
        'section': 'team',
    }
    return render(request, 'team/manage_team.html', context)


@login_required
@role_required(['admin'])
def edit_team_member_view(request, member_id):
    """Edit existing team member"""
    
    team_member = get_object_or_404(TeamMember, id=member_id)
    
    if request.method == 'POST':
        form = TeamMemberForm(request.POST, request.FILES, instance=team_member)
        if form.is_valid():
            form.save()
            messages.success(request, f'Team member {team_member.full_name} updated successfully.')
            return redirect('team:manage_team')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = TeamMemberForm(instance=team_member)
    
    context = {
        'form': form,
        'team_member': team_member,
        'section': 'team',
    }
    return render(request, 'team/edit_team_member.html', context)


@login_required
@role_required(['admin'])
def delete_team_member_view(request, member_id):
    """Delete team member and revert user role to customer"""
    
    team_member = get_object_or_404(TeamMember, id=member_id)
    
    if request.method == 'POST':
        # Get the associated user
        user = team_member.user
        
        # Revert user role to customer if they were a team member
        if user and user.role == 'team_member':
            user.role = 'customer'
            user.team_permissions = {}
            user.save()
            messages.info(request, f'User {user.email} role reverted to customer.')
        
        # Delete the team member record
        team_member.delete()
        messages.success(request, 'Team member removed successfully.')
    
    return redirect('team:manage_team')


# ==================== TASK MANAGEMENT ====================

@login_required
@role_required(['admin', 'team_member'])
def team_tasks_view(request):
    """View team tasks"""
    
    if request.user.role == 'admin':
        tasks = TeamTask.objects.all()
    else:
        tasks = TeamTask.objects.filter(assigned_to=request.user)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        tasks = tasks.filter(status=status)
    
    # Filter by priority
    priority = request.GET.get('priority')
    if priority:
        tasks = tasks.filter(priority=priority)
    
    tasks = tasks.order_by('-priority', 'due_date')
    
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total': tasks.count(),
        'pending': tasks.filter(status='pending').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'completed': tasks.filter(status='completed').count(),
        'overdue': tasks.filter(status__in=['pending', 'in_progress'], due_date__lt=timezone.now()).count(),
    }
    
    context = {
        'tasks': page_obj,
        'stats': stats,
        'current_status': status,
        'current_priority': priority,
        'section': 'tasks',
    }
    return render(request, 'team/tasks.html', context)


@login_required
@role_required(['admin', 'team_member'])
def create_task_view(request):
    """Create new task"""
    
    if request.method == 'POST':
        form = TeamTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.assigned_by = request.user
            task.save()
            
            # Notify assigned team member
            NotificationManager.send_notification(
                user=task.assigned_to,
                title=f"New Task Assigned: {task.title}",
                message=f"You have been assigned a new task. Priority: {task.get_priority_display()}. Due: {task.due_date.strftime('%Y-%m-%d %H:%M')}",
                notification_type='system',
                priority='high' if task.priority in ['high', 'urgent'] else 'medium',
                link=reverse('team:task_detail', args=[task.id])
            )
            
            messages.success(request, f'Task "{task.title}" created and assigned to {task.assigned_to.email}.')
            return redirect('team:tasks')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = TeamTaskForm()
    
    context = {
        'form': form,
        'section': 'tasks',
    }
    return render(request, 'team/create_task.html', context)


@login_required
@role_required(['admin', 'team_member'])
def task_detail_view(request, task_id):
    """View task details and update status"""
    
    task = get_object_or_404(TeamTask, id=task_id)
    
    # Check permission
    if request.user.role not in ['admin'] and task.assigned_to != request.user:
        messages.error(request, 'Permission denied. You can only view your own tasks.')
        return redirect('team:tasks')
    
    if request.method == 'POST':
        form = TaskStatusForm(request.POST, instance=task)
        if form.is_valid():
            old_status = task.status
            task = form.save()
            
            if task.status == 'completed' and old_status != 'completed':
                task.mark_completed()
                messages.success(request, '🎉 Task marked as completed! Good job!')
                
                # Notify task creator that task is completed
                if task.assigned_by:
                    NotificationManager.send_notification(
                        user=task.assigned_by,
                        title=f"Task Completed: {task.title}",
                        message=f"Task assigned to {task.assigned_to.email} has been completed.",
                        notification_type='system',
                        priority='medium',
                        link=reverse('team:task_detail', args=[task.id])
                    )
            else:
                messages.success(request, f'Task status updated to {task.get_status_display()}.')
            
            return redirect('team:task_detail', task_id=task.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = TaskStatusForm(instance=task)
    
    context = {
        'task': task,
        'form': form,
        'section': 'tasks',
    }
    return render(request, 'team/task_detail.html', context)


@login_required
@role_required(['admin'])
def delete_task_view(request, task_id):
    """Delete task (admin only)"""
    
    task = get_object_or_404(TeamTask, id=task_id)
    
    if request.method == 'POST':
        task_title = task.title
        task.delete()
        messages.success(request, f'Task "{task_title}" deleted successfully.')
    
    return redirect('team:tasks')