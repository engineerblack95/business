from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list_view, name='list'),
    path('preferences/', views.notification_preferences_view, name='preferences'),
    path('mark-read/<uuid:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('delete/<uuid:notification_id>/', views.delete_notification, name='delete'),
    path('api/', views.api_notifications, name='api'),
]