from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import WithdrawalRequest


class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), 
        required=True
    )
    phone_number = forms.CharField(
        max_length=20, 
        widget=forms.TextInput(attrs={'class': 'form-control'}), 
        required=True
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}), 
        required=False
    )
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if len(phone) < 10:
            raise ValidationError("Please enter a valid phone number")
        return phone


class PaymentSimulationForm(forms.Form):
    mobile_money_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+250 78 XXX XXXX'
        }),
        label="Mobile Money Number"
    )
    
    def clean_mobile_money_number(self):
        number = self.cleaned_data.get('mobile_money_number')
        if not number:
            raise ValidationError('Mobile money number is required')
        digits = ''.join(filter(str.isdigit, number))
        if len(digits) < 10 or len(digits) > 12:
            raise ValidationError('Please enter a valid phone number (10-12 digits)')
        return number


class WithdrawalRequestForm(forms.ModelForm):
    """Form for admin to request commission withdrawal - FIXED to match model"""
    
    class Meta:
        model = WithdrawalRequest
        # FIXED: Changed 'mobile_money_number' to 'phone_number' to match model
        fields = ['amount', 'phone_number', 'payment_method', 'bank_name', 'account_number', 'account_name', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter amount to withdraw',
                'min': '1000',
                'step': '100'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '0788 123 456'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-select'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank Name'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account Number'
            }),
            'account_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account Holder Name'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes (optional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.available_commission = kwargs.pop('available_commission', None)
        super().__init__(*args, **kwargs)
        
        # Make payment_method required
        self.fields['payment_method'].required = True
        self.fields['payment_method'].choices = WithdrawalRequest.PAYMENT_METHODS
        
        # Initially hide bank fields - will be shown via JS
        self.fields['bank_name'].required = False
        self.fields['account_number'].required = False
        self.fields['account_name'].required = False
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        
        if amount:
            if amount < 1000:
                raise ValidationError('Minimum withdrawal amount is 1,000 FRW')
            
            if self.available_commission and amount > self.available_commission:
                raise ValidationError(
                    f'Amount exceeds available commission ({self.available_commission:,.0f} FRW)'
                )
        
        return amount
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        payment_method = self.cleaned_data.get('payment_method')
        
        if payment_method == 'mobile_money' and not phone:
            raise ValidationError('Mobile money number is required')
        
        if phone:
            digits = ''.join(filter(str.isdigit, phone))
            if len(digits) < 10 or len(digits) > 12:
                raise ValidationError('Please enter a valid phone number (10-12 digits)')
        
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        bank_name = cleaned_data.get('bank_name')
        account_number = cleaned_data.get('account_number')
        account_name = cleaned_data.get('account_name')
        
        # Validate bank fields if payment method is bank transfer
        if payment_method == 'bank_transfer':
            if not bank_name:
                self.add_error('bank_name', 'Bank name is required')
            if not account_number:
                self.add_error('account_number', 'Account number is required')
            if not account_name:
                self.add_error('account_name', 'Account holder name is required')
        
        return cleaned_data


class OrderFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('', 'All'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES, 
        required=False, 
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False, 
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    date_to = forms.DateField(
        required=False, 
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    order_id = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Order ID'})
    )