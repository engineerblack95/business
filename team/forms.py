from django import forms
from django.core.exceptions import ValidationError
from .models import TeamMember, TeamTask
from accounts.models import User


class TeamMemberForm(forms.ModelForm):
    """Form for managing team members - User must already be registered"""
    
    # Add user selection field (must exist in database)
    user_email = forms.EmailField(
        label="Registered User Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email of registered user'
        }),
        help_text="User must already have an account on the website"
    )
    
    # Permission fields
    can_view_orders = forms.BooleanField(required=False, initial=False, label="View Orders")
    can_view_products = forms.BooleanField(required=False, initial=False, label="View Products")
    can_edit_products = forms.BooleanField(required=False, initial=False, label="Edit Products")
    can_approve_products = forms.BooleanField(required=False, initial=False, label="Approve Products")
    can_manage_suppliers = forms.BooleanField(required=False, initial=False, label="Manage Suppliers")
    can_view_logs = forms.BooleanField(required=False, initial=False, label="View Activity Logs")
    can_view_financial = forms.BooleanField(required=False, initial=False, label="View Financial Data")
    
    class Meta:
        model = TeamMember
        fields = [
            'user_email', 'full_name', 'position', 'custom_position', 'email', 'phone',
            'profile_image', 'bio', 'expertise', 'achievements',
            'linkedin', 'twitter', 'facebook', 'instagram',
            'display_order', 'is_active', 'featured'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'custom_position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Custom position title'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Display Email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Short biography...'}),
            'expertise': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Customer Service, Technical Support, Logistics'}),
            'achievements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Key achievements...'}),
            'linkedin': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://linkedin.com/in/username'}),
            'twitter': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://twitter.com/username'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://facebook.com/username'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://instagram.com/username'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing team member, populate user_email and permissions
        if self.instance and self.instance.pk and self.instance.user:
            self.initial['user_email'] = self.instance.user.email
            self.initial['email'] = self.instance.user.email
            self.initial['phone'] = self.instance.user.phone
            
            # Populate permissions from user's team_permissions
            if hasattr(self.instance.user, 'team_permissions'):
                perms = self.instance.user.team_permissions
                self.initial['can_view_orders'] = perms.get('can_view_orders', False)
                self.initial['can_view_products'] = perms.get('can_view_products', False)
                self.initial['can_edit_products'] = perms.get('can_edit_products', False)
                self.initial['can_approve_products'] = perms.get('can_approve_products', False)
                self.initial['can_manage_suppliers'] = perms.get('can_manage_suppliers', False)
                self.initial['can_view_logs'] = perms.get('can_view_logs', False)
                self.initial['can_view_financial'] = perms.get('can_view_financial', False)
            
            # Make user_email read-only when editing
            self.fields['user_email'].widget.attrs['readonly'] = True
            self.fields['user_email'].help_text = "User email cannot be changed after creation"
    
    def clean_user_email(self):
        """Validate that the email exists in User model"""
        email = self.cleaned_data.get('user_email')
        
        if not email:
            raise ValidationError('User email is required')
        
        # If editing and email hasn't changed, allow it
        if self.instance and self.instance.pk and self.instance.user:
            if self.instance.user.email == email:
                return email
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValidationError(
                f'User with email "{email}" does not exist. '
                'The user must register as a customer first before becoming a team member.'
            )
        
        # Check if user is already a team member or admin
        if user.role in ['team_member', 'admin']:
            raise ValidationError(
                f'User "{email}" is already a {user.role}. '
                'Cannot assign as team member again.'
            )
        
        return email
    
    def save(self, commit=True):
        """Save team member and update associated user"""
        instance = super().save(commit=False)
        
        # Get the existing user
        email = self.cleaned_data.get('user_email')
        user = User.objects.get(email=email)
        
        # Link the user to team member
        instance.user = user
        
        # Update user's role to team_member if not already
        if user.role != 'team_member':
            user.role = 'team_member'
        
        # Update user's team permissions
        user.team_permissions = {
            'can_view_orders': self.cleaned_data.get('can_view_orders', False),
            'can_view_products': self.cleaned_data.get('can_view_products', False),
            'can_edit_products': self.cleaned_data.get('can_edit_products', False),
            'can_approve_products': self.cleaned_data.get('can_approve_products', False),
            'can_manage_suppliers': self.cleaned_data.get('can_manage_suppliers', False),
            'can_view_logs': self.cleaned_data.get('can_view_logs', False),
            'can_view_financial': self.cleaned_data.get('can_view_financial', False),
        }
        
        # Update user's display name if provided
        if self.cleaned_data.get('full_name'):
            user.full_name = self.cleaned_data.get('full_name')
        
        # Update user's phone if provided
        if self.cleaned_data.get('phone'):
            user.phone = self.cleaned_data.get('phone')
        
        user.save()
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


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
        # Only show team members and admins in assignment list
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