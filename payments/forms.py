from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import WithdrawalRequest, PaymentMethod

class MobileMoneyPaymentForm(forms.Form):
    """Form for mobile money payment"""
    
    mobile_money_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+250 78 XXX XXXX',
            'pattern': '^\+?[0-9]{10,15}$'
        }),
        label="Mobile Money Number"
    )
    
    provider = forms.ChoiceField(
        choices=[
            ('mtn', 'MTN Mobile Money'),
            ('airtel', 'Airtel Money'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Select Provider"
    )
    
    def clean_mobile_money_number(self):
        number = self.cleaned_data.get('mobile_money_number')
        # Remove spaces and special characters
        number = ''.join(filter(str.isdigit, number))
        
        # Basic Rwanda mobile money validation
        if len(number) < 10 or len(number) > 12:
            raise ValidationError('Please enter a valid phone number')
        
        return number


class BankTransferForm(forms.Form):
    """Form for bank transfer payment"""
    
    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    account_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class':form-control'})
    )
    account_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    transfer_reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def clean_account_number(self):
        number = self.cleaned_data.get('account_number')
        if not number:
            raise ValidationError('Account number is required')
        return number


class WithdrawalRequestForm(forms.ModelForm):
    """Form for admin to request commission withdrawal"""
    
    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'payment_method', 'mobile_money_number']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter amount to withdraw',
                'min': '1000',
                'step': '100'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
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
        
        if self.available_commission and amount > self.available_commission:
            raise ValidationError(f'Amount exceeds available commission ({self.available_commission} FRW)')
        
        if amount < 1000:
            raise ValidationError('Minimum withdrawal amount is 1,000 FRW')
        
        return amount
    
    def clean_mobile_money_number(self):
        number = self.cleaned_data.get('mobile_money_number')
        if not number:
            raise ValidationError('Mobile money number is required')
        # Basic validation
        digits = ''.join(filter(str.isdigit, number))
        if len(digits) < 10:
            raise ValidationError('Please enter a valid phone number')
        return number


class PaymentFilterForm(forms.Form):
    """Filter payments in admin panel"""
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(PaymentTransaction.TRANSACTION_STATUS),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    payment_method = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(PaymentTransaction.PAYMENT_METHODS),
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


class SupplierPayoutFilterForm(forms.Form):
    """Filter supplier payouts"""
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(SupplierPayout.PAYOUT_STATUS),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    supplier = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search supplier...'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )