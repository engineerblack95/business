from django import forms
from django.contrib.auth import get_user_model
from products.models import Category
from notifications.models import Notification

User = get_user_model()

class TeamMemberForm(forms.ModelForm):
    """Form for admin to create/edit team members"""
    
    permissions = forms.MultipleChoiceField(
        choices=[
            ('can_view_products', 'View Products'),
            ('can_edit_products', 'Edit Products'),
            ('can_approve_products', 'Approve Products'),
            ('can_view_orders', 'View Orders'),
            ('can_manage_suppliers', 'Manage Suppliers'),
            ('can_view_logs', 'View System Logs'),
            ('can_view_financial', 'View Financial Data'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = User
        fields = ['email', 'full_name', 'phone', 'permissions']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'team_member'
        
        if commit:
            user.save()
            # Save permissions as JSON
            permissions_dict = {perm: True for perm in self.cleaned_data['permissions']}
            user.team_permissions = permissions_dict
            user.save()
        
        return user


class NotificationFilterForm(forms.Form):
    """Filter notifications"""
    
    notification_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + Notification.NOTIFICATION_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    is_read = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('true', 'Unread Only'), ('false', 'Read Only')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )


class ProductQuickEditForm(forms.Form):
    """Quick edit product stock and price from dashboard"""
    
    product_id = forms.CharField(widget=forms.HiddenInput())
    exact_quantity = forms.IntegerField(min_value=0, required=False)
    base_price = forms.DecimalField(min_value=0, required=False, decimal_places=2)
    
    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('exact_quantity') and not cleaned_data.get('base_price'):
            raise forms.ValidationError('At least one field must be updated')
        return cleaned_data


class OrderFilterForm(forms.Form):
    """Filter orders in dashboard"""
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Orders')] + [
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('processing', 'Processing'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_range = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Time'),
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('year', 'This Year'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )