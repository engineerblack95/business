from django.urls import path
from . import views

app_name = 'team'

urlpatterns = [
    # Public
    path('about/', views.about_view, name='about'),
    
    # Admin team management
    path('manage/', views.manage_team_view, name='manage_team'),
    path('edit/<uuid:member_id>/', views.edit_team_member_view, name='edit_team_member'),
    path('delete/<uuid:member_id>/', views.delete_team_member_view, name='delete_team_member'),
    
    # Tasks
    path('tasks/', views.team_tasks_view, name='tasks'),
    path('tasks/create/', views.create_task_view, name='create_task'),
    path('tasks/<uuid:task_id>/', views.task_detail_view, name='task_detail'),
    path('tasks/<uuid:task_id>/delete/', views.delete_task_view, name='delete_task'),
]