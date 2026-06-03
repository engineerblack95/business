from django import forms
from django.core.exceptions import ValidationError
from .models import Product, Category, ProductReview
from decimal import Decimal

class ProductForm(forms.ModelForm):
    """Form for creating and updating products"""
    
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'subcategory', 'description', 'short_description',
            'base_price', 'exact_quantity', 'brand', 'model_number', 
            'warranty_months', 'main_image', 'tags', 'meta_title', 'meta_description',
            'low_stock_threshold'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter product name'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'subcategory': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Detailed product description'}),
            'short_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief description'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Price excluding VAT', 'step': '0.01'}),
            'exact_quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Exact stock quantity', 'min': '0'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brand name'}),
            'model_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Model number'}),
            'warranty_months': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'main_image': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),  # Added for Cloudinary
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., laptop, gaming, dell'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SEO title'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'SEO description'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['subcategory'].queryset = Category.objects.filter(is_active=True)
        self.fields['subcategory'].required = False
        # Make main_image not required for updates
        if self.instance and self.instance.pk:
            self.fields['main_image'].required = False
    
    def clean_base_price(self):
        base_price = self.cleaned_data.get('base_price')
        if base_price <= 0:
            raise ValidationError('Price must be greater than 0')
        return base_price
    
    def clean_exact_quantity(self):
        quantity = self.cleaned_data.get('exact_quantity')
        if quantity < 0:
            raise ValidationError('Quantity cannot be negative')
        return quantity
    
    def clean_tags(self):
        tags = self.cleaned_data.get('tags', '')
        if tags:
            tags = ','.join([tag.strip().lower() for tag in tags.split(',') if tag.strip()])
        return tags


class ProductApprovalForm(forms.ModelForm):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Reason for rejection'}),
        required=False
    )
    
    class Meta:
        model = Product
        fields = ['status', 'rejection_reason']
        widgets = {'status': forms.Select(attrs={'class': 'form-select'})}
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')
        if status == 'rejected' and not rejection_reason:
            raise ValidationError('Please provide a reason for rejection')
        return cleaned_data


class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}, choices=[(i, f"{i} stars") for i in range(1, 6)]),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Review title'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Share your experience'}),
        }


class ProductSearchForm(forms.Form):
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search products...'}))
    category = forms.ModelChoiceField(queryset=Category.objects.filter(is_active=True), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    min_price = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min price'}))
    max_price = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max price'}))
    in_stock_only = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    sort_by = forms.ChoiceField(required=False, choices=[
        ('newest', 'Newest First'),
        ('price_low', 'Price: Low to High'),
        ('price_high', 'Price: High to Low'),
        ('popular', 'Most Popular'),
        ('rating', 'Highest Rated'),
    ], widget=forms.Select(attrs={'class': 'form-select'}))
    
    def clean(self):
        cleaned_data = super().clean()
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')
        if min_price and max_price and min_price > max_price:
            raise ValidationError('Minimum price cannot be greater than maximum price')
        return cleaned_data


class ProductStockUpdateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['exact_quantity']
        widgets = {'exact_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'})}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['exact_quantity'].label = "Current Stock Quantity"
        self.fields['exact_quantity'].help_text = "Enter exact number of units available"


class BulkProductUploadForm(forms.Form):
    csv_file = forms.FileField(widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'}))
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        if not csv_file.name.endswith('.csv'):
            raise ValidationError('Please upload a CSV file')
        if csv_file.size > 5 * 1024 * 1024:
            raise ValidationError('File size must be less than 5MB')
        return csv_file  # Fixed: removed trailing comma