from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse

from accounts.decorators import role_required, permission_required
from .models import TeamMember, TeamTask, TeamActivity
from .forms import TeamMemberForm, TeamTaskForm, TaskStatusForm
from dashboard.utils.notifications import NotificationManager


def about_view(request):
    """Public about page showing team members"""
    
    team_members = TeamMember.objects.filter(is_active=True).order_by('display_order')
    
    # Get leadership team (featured)
    leadership = team_members.filter(featured=True)
    other_members = team_members.filter(featured=False)
    
    context = {
        'leadership': leadership,
        'team_members': other_members,
        'total_members': team_members.count(),
    }
    return render(request, 'team/about.html', context)


@login_required
@role_required(['admin'])
def manage_team_view(request):
    """Admin manage team members"""
    
    if request.method == 'POST':
        form = TeamMemberForm(request.POST, request.FILES)
        if form.is_valid():
            team_member = form.save()
            messages.success(request, f'Team member {team_member.full_name} added successfully.')
            return redirect('team:manage_team')
    else:
        form = TeamMemberForm()
    
    team_members = TeamMember.objects.all().order_by('display_order')
    
    context = {
        'form': form,
        'team_members': team_members,
        'section': 'team',
    }
    return render(request, 'team/manage_team.html', context)


@login_required
@role_required(['admin'])
def edit_team_member_view(request, member_id):
    """Edit team member"""
    
    team_member = get_object_or_404(TeamMember, id=member_id)
    
    if request.method == 'POST':
        form = TeamMemberForm(request.POST, request.FILES, instance=team_member)
        if form.is_valid():
            form.save()
            messages.success(request, f'Team member {team_member.full_name} updated successfully.')
            return redirect('team:manage_team')
    else:
        form = TeamMemberForm(instance=team_member)
    
    context = {
        'form': form,
        'team_member': team_member,
    }
    return render(request, 'team/edit_team_member.html', context)


@login_required
@role_required(['admin'])
def delete_team_member_view(request, member_id):
    """Delete team member"""
    
    team_member = get_object_or_404(TeamMember, id=member_id)
    
    if request.method == 'POST':
        team_member.delete()
        messages.success(request, 'Team member removed successfully.')
    
    return redirect('team:manage_team')


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
                message=f"You have been assigned a new task. Priority: {task.get_priority_display()}. Due: {task.due_date}",
                notification_type='system',
                priority='high' if task.priority in ['high', 'urgent'] else 'medium',
                link=f'/team/tasks/'
            )
            
            messages.success(request, f'Task "{task.title}" created and assigned.')
            return redirect('team:tasks')
    else:
        form = TeamTaskForm()
    
    context = {'form': form}
    return render(request, 'team/create_task.html', context)


@login_required
@role_required(['admin', 'team_member'])
def task_detail_view(request, task_id):
    """View task details"""
    
    task = get_object_or_404(TeamTask, id=task_id)
    
    # Check permission
    if request.user.role not in ['admin'] and task.assigned_to != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('team:tasks')
    
    if request.method == 'POST':
        form = TaskStatusForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()
            
            if task.status == 'completed':
                task.mark_completed()
                messages.success(request, 'Task marked as completed!')
            
            return redirect('team:task_detail', task_id=task.id)
    else:
        form = TaskStatusForm(instance=task)
    
    context = {
        'task': task,
        'form': form,
    }
    return render(request, 'team/task_detail.html', context)


@login_required
@role_required(['admin'])
def delete_task_view(request, task_id):
    """Delete task"""
    
    task = get_object_or_404(TeamTask, id=task_id)
    
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Task deleted successfully.')
    
    return redirect('team:tasks')