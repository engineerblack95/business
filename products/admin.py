from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, ProductImage, ProductReview, Wishlist

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category_type', 'is_active', 'order']
    list_filter = ['category_type', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['order', 'is_active']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    fields = ['image_preview', 'image', 'alt_text', 'order']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Preview'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['image_preview', 'name', 'owner', 'get_stock_display', 'final_price', 'status', 'is_supplier_product', 'sales_count']
    list_filter = ['status', 'is_supplier_product', 'category', 'created_at']
    search_fields = ['name', 'description', 'brand', 'owner__email']
    readonly_fields = ['slug', 'vat_amount', 'final_price', 'views_count', 'sales_count', 'rating']
    inlines = [ProductImageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'description', 'short_description')
        }),
        ('Pricing & Tax', {
            'fields': ('base_price', 'vat_amount', 'final_price')
        }),
        ('Stock Management', {
            'fields': ('exact_quantity', 'low_stock_threshold')
        }),
        ('Ownership', {
            'fields': ('owner', 'is_supplier_product')
        }),
        ('Approval', {
            'fields': ('status', 'approval_status', 'approved_by', 'approved_at', 'rejection_reason')
        }),
        ('Specifications', {
            'fields': ('brand', 'model_number', 'warranty_months')
        }),
        ('Media & SEO', {
            'fields': ('main_image', 'tags', 'meta_title', 'meta_description')
        }),
        ('Metrics', {
            'fields': ('views_count', 'sales_count', 'rating', 'rating_count'),
            'classes': ('collapse',)
        }),
    )
    
    def image_preview(self, obj):
        if obj.main_image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 8px;" />', obj.main_image.url)
        return "No Image"
    image_preview.short_description = 'Image'
    
    def get_stock_display(self, obj):
        if obj.exact_quantity <= obj.low_stock_threshold and obj.exact_quantity > 0:
            color = 'orange'
        elif obj.exact_quantity == 0:
            color = 'red'
        else:
            color = 'green'
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.exact_quantity)
    get_stock_display.short_description = 'Stock'


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'rating', 'title', 'is_verified_purchase', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'is_verified_purchase']
    search_fields = ['product__name', 'customer__email', 'title', 'comment']
    list_editable = ['is_approved']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['customer', 'product', 'added_at']
    list_filter = ['added_at']
    search_fields = ['customer__email', 'product__name']