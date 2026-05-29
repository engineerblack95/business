import django_filters
from django.db.models import Q
from .models import Product, Category

class ProductFilter(django_filters.FilterSet):
    """Advanced filtering for products"""
    
    query = django_filters.CharFilter(method='filter_search', label='Search')
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.filter(is_active=True))
    min_price = django_filters.NumberFilter(field_name='final_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='final_price', lookup_expr='lte')
    brand = django_filters.CharFilter(lookup_expr='icontains')
    in_stock_only = django_filters.BooleanFilter(method='filter_in_stock', label='In Stock Only')
    
    class Meta:
        model = Product
        fields = ['category', 'brand', 'min_price', 'max_price']
    
    def filter_search(self, queryset, name, value):
        """Search by name, description, tags, brand"""
        if value:
            return queryset.filter(
                Q(name__icontains=value) |
                Q(description__icontains=value) |
                Q(tags__icontains=value) |
                Q(brand__icontains=value) |
                Q(short_description__icontains=value)
            )
        return queryset
    
    def filter_in_stock(self, queryset, name, value):
        """Filter products that are in stock"""
        if value:
            return queryset.filter(exact_quantity__gt=0)
        return queryset