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
    """Form for admin to request commission withdrawal"""
    
    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'mobile_money_number']  # Only use fields that exist in the model
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter amount to withdraw',
                'min': '1000',
                'step': '100'
            }),
            'mobile_money_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+250xxxxxxxxx'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.available_commission = kwargs.pop('available_commission', None)
        super().__init__(*args, **kwargs)
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        
        if amount and self.available_commission:
            if amount > self.available_commission:
                raise ValidationError(
                    f'Amount exceeds available commission ({self.available_commission:,.0f} FRW)'
                )
        
        if amount and amount < 1000:
            raise ValidationError('Minimum withdrawal amount is 1,000 FRW')
        
        return amount
    
    def clean_mobile_money_number(self):
        number = self.cleaned_data.get('mobile_money_number')
        if not number:
            raise ValidationError('Mobile money number is required')
        digits = ''.join(filter(str.isdigit, number))
        if len(digits) < 10 or len(digits) > 12:
            raise ValidationError('Please enter a valid phone number (10-12 digits)')
        return number


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