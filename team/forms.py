from django import forms
from .models import TeamMember, TeamTask

class TeamMemberForm(forms.ModelForm):
    """Form for managing team members"""
    
    class Meta:
        model = TeamMember
        fields = [
            'full_name', 'position', 'custom_position', 'email', 'phone',
            'profile_image', 'bio', 'expertise', 'achievements',
            'linkedin', 'twitter', 'facebook', 'instagram',
            'display_order', 'is_active', 'featured'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'custom_position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Custom position title'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'expertise': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Customer Service, Technical Support, Logistics'}),
            'achievements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'linkedin': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://linkedin.com/in/username'}),
            'twitter': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://twitter.com/username'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/username'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://instagram.com/username'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
            self.fields['phone'].initial = self.instance.user.phone


class TeamTaskForm(forms.ModelForm):
    """Form for creating/editing team tasks"""
    
    class Meta:
        model = TeamTask
        fields = ['title', 'description', 'assigned_to', 'priority', 'due_date', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import User
        self.fields['assigned_to'].queryset = User.objects.filter(role__in=['admin', 'team_member'])


class TaskStatusForm(forms.ModelForm):
    """Form for updating task status"""
    
    class Meta:
        model = TeamTask
        fields = ['status', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }