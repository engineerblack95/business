from django import forms
from django.core.exceptions import ValidationError
from .models import SupplierApplication, SupplierProfile
from products.models import Category

class SupplierApplicationForm(forms.ModelForm):
    """Form for customers to apply as suppliers"""
    
    interested_categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'size': '5'
        }),
        required=False,
        help_text="Select categories you're interested in selling"
    )
    
    terms_agreed = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I agree to the supplier terms and conditions"
    )
    
    class Meta:
        model = SupplierApplication
        fields = [
            'business_name', 'business_type', 'tax_id', 'registration_number',
            'business_phone', 'business_email', 'business_address', 'business_city',
            'business_country', 'website', 'years_in_business', 'estimated_monthly_volume',
            'interested_categories', 'notes',
            'business_license', 'id_document', 'tax_clearance', 'bank_statement'
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your registered business name'
            }),
            'business_type': forms.Select(attrs={'class': 'form-select'}),
            'tax_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tax identification number (if applicable)'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Business registration number'
            }),
            'business_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+25078xxxxxxxx'
            }),
            'business_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'business@example.com'
            }),
            'business_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Complete business address'
            }),
            'business_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'business_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-website.com'
            }),
            'years_in_business': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'estimated_monthly_volume': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Expected monthly sales in FRW',
                'step': '1000'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any additional information about your business'
            }),
        }
    
    def clean_business_phone(self):
        phone = self.cleaned_data.get('business_phone')
        if phone and not phone.startswith('+') and not phone.startswith('0'):
            raise ValidationError('Phone number must start with + or country code')
        return phone
    
    def clean_estimated_monthly_volume(self):
        volume = self.cleaned_data.get('estimated_monthly_volume')
        if volume and volume < 0:
            raise ValidationError('Estimated monthly volume cannot be negative')
        return volume


class SupplierApplicationReviewForm(forms.ModelForm):
    """Form for admin to review supplier applications"""
    
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Reason for rejection (required if rejecting)'
        }),
        required=False
    )
    
    additional_info_request = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Additional information required from supplier'
        }),
        required=False
    )
    
    class Meta:
        model = SupplierApplication
        fields = ['status', 'rejection_reason', 'additional_info_request']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'})
        }
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')
        additional_info = cleaned_data.get('additional_info_request')
        
        if status == 'rejected' and not rejection_reason:
            raise ValidationError('Please provide a reason for rejection')
        
        if status == 'additional_info' and not additional_info:
            raise ValidationError('Please specify what additional information is needed')
        
        return cleaned_data


class SupplierProfileForm(forms.ModelForm):
    """Form for suppliers to update their profile"""
    
    class Meta:
        model = SupplierProfile
        fields = [
            'business_name', 'logo', 'cover_image', 'description',
            'business_phone', 'business_email', 'business_address',
            'business_city', 'business_country', 'website',
            'payment_method', 'mobile_money_number',
            'bank_account_name', 'bank_account_number', 'bank_name'
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Tell customers about your business...'
            }),
            'business_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'business_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'business_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'business_city': forms.TextInput(attrs={'class': 'form-control'}),
            'business_country': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'mobile_money_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean_mobile_money_number(self):
        number = self.cleaned_data.get('mobile_money_number')
        if number and not number.startswith('+') and not number.startswith('0'):
            raise ValidationError('Please enter a valid phone number')
        return number


class SupplierFilterForm(forms.Form):
    """Form for filtering suppliers"""
    
    verification_status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(SupplierProfile.VERIFICATION_STATUS),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    min_rating = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.5',
            'placeholder': 'Min rating'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by business name or email...'
        })
    )