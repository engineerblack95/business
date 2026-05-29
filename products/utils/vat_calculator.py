from decimal import Decimal
from django.conf import settings

class VATCalculator:
    """Calculate VAT for products"""
    
    VAT_RATE = Decimal(str(getattr(settings, 'VAT_RATE', 18))) / Decimal('100')
    
    @classmethod
    def calculate_vat(cls, base_price):
        """Calculate VAT amount from base price"""
        if not base_price:
            return Decimal('0.00')
        return (base_price * cls.VAT_RATE).quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_final_price(cls, base_price):
        """Calculate final price including VAT"""
        if not base_price:
            return Decimal('0.00')
        return (base_price + cls.calculate_vat(base_price)).quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_base_price_from_final(cls, final_price):
        """Calculate base price from final price (including VAT)"""
        if not final_price:
            return Decimal('0.00')
        return (final_price / (Decimal('1') + cls.VAT_RATE)).quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_vat_from_final(cls, final_price):
        """Calculate VAT amount from final price"""
        if not final_price:
            return Decimal('0.00')
        base_price = cls.calculate_base_price_from_final(final_price)
        return final_price - base_price
    
    @classmethod
    def format_price(cls, amount, currency='FRW'):
        """Format price with currency"""
        return f"{amount:,.0f} {currency}"