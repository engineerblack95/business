"""
Wallet Service - Core business logic for wallet operations
Handles all wallet transactions, splits, withdrawals, and balance management
"""

from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q
from typing import Dict, Any, Optional, List, Tuple

from ..models import (
    Order, OrderItem, Wallet, WalletTransaction, 
    WithdrawalRequest, CommissionEarning, SupplierPayout
)
from accounts.models import User


class WalletService:
    """
    Professional Wallet Service for managing:
    - Automatic order payment splitting
    - Balance management for admin, suppliers, and tax
    - Withdrawal request processing
    - Transaction history and reporting
    """
    
    # Constants
    MINIMUM_WITHDRAWAL = Decimal('5000')
    COMMISSION_RATE = Decimal('0.07')  # 7%
    VAT_RATE = Decimal('0.18')  # 18%
    
    # ============================================================
    # WALLET INITIALIZATION & MANAGEMENT
    # ============================================================
    
    @classmethod
    def get_or_create_wallet(cls, user: Optional[User], wallet_type: str) -> Wallet:
        """
        Get or create a wallet for a user
        
        Args:
            user: User object (can be None for system wallets)
            wallet_type: 'admin', 'supplier', or 'tax'
        
        Returns:
            Wallet instance
        """
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            wallet_type=wallet_type,
            defaults={
                'balance': Decimal('0.00'),
                'pending_balance': Decimal('0.00')
            }
        )
        return wallet
    
    @classmethod
    def get_admin_wallet(cls) -> Wallet:
        """Get the admin commission wallet"""
        admin_user = User.objects.filter(role='admin').first()
        if not admin_user:
            raise ValueError("No admin user found in system")
        return cls.get_or_create_wallet(admin_user, 'admin')
    
    @classmethod
    def get_supplier_wallet(cls, supplier: User) -> Wallet:
        """Get a supplier's earnings wallet"""
        return cls.get_or_create_wallet(supplier, 'supplier')
    
    @classmethod
    def get_tax_wallet(cls) -> Wallet:
        """Get the system tax wallet (for government VAT)"""
        return cls.get_or_create_wallet(None, 'tax')
    
    @classmethod
    def get_wallet_balance(cls, user: User, wallet_type: str = 'supplier') -> Dict[str, Any]:
        """
        Get wallet balance for a user
        
        Returns:
            Dict with 'balance', 'pending', 'total'
        """
        try:
            wallet = Wallet.objects.get(user=user, wallet_type=wallet_type)
            return {
                'balance': wallet.balance,
                'pending': wallet.pending_balance,
                'total': wallet.balance + wallet.pending_balance,
                'wallet_id': str(wallet.id),
                'wallet_type': wallet.wallet_type
            }
        except Wallet.DoesNotExist:
            return {
                'balance': Decimal('0.00'),
                'pending': Decimal('0.00'),
                'total': Decimal('0.00'),
                'wallet_id': None,
                'wallet_type': wallet_type
            }
    
    # ============================================================
    # ORDER PAYMENT SPLITTING (CORE LOGIC)
    # ============================================================
    
    @classmethod
    @transaction.atomic
    def process_order_split(cls, order: Order) -> Dict[str, Any]:
        """
        Automatically split order payment into appropriate wallets
        
        This is the CORE function called when an order is paid.
        It distributes funds to:
        - Supplier wallets (for their products)
        - Admin commission wallet (7% of supplier products)
        - Tax wallet (18% VAT on ALL products)
        
        Args:
            order: The paid Order object
        
        Returns:
            Dict with success status and summary of distributions
        """
        
        if order.payment_status not in ['paid', 'simulated']:
            return {
                'success': False,
                'error': 'Order is not paid yet',
                'distributions': []
            }
        
        # Check if already processed
        existing_txns = WalletTransaction.objects.filter(
            order=order,
            category__in=['commission', 'supplier_payout', 'vat_collection', 'product_sale']
        ).exists()
        
        if existing_txns:
            return {
                'success': False,
                'error': 'Order has already been processed for wallet distribution',
                'distributions': []
            }
        
        distributions = []
        admin_wallet = cls.get_admin_wallet()
        tax_wallet = cls.get_tax_wallet()
        
        # Process each order item
        for order_item in order.items.select_related('product', 'product__owner').all():
            
            item_vat = order_item.vat_amount * order_item.quantity  # 18,000 FRW for 100,000 base
            
            # === 1. ALWAYS: Add VAT to Tax Wallet ===
            tax_wallet.add_balance(item_vat)
            vat_transaction = WalletTransaction.objects.create(
                wallet=tax_wallet,
                order=order,
                order_item=order_item,
                amount=item_vat,
                transaction_type='credit',
                category='vat_collection',
                status='completed',
                description=f"VAT (18%) collected from order #{order.order_number} - {order_item.product.name}",
                metadata={
                    'product_name': order_item.product.name,
                    'quantity': order_item.quantity,
                    'base_price': float(order_item.base_price),
                    'vat_rate': 18
                }
            )
            distributions.append({
                'type': 'vat',
                'recipient': 'Government (Tax)',
                'amount': item_vat,
                'transaction_id': str(vat_transaction.id)
            })
            
            # === 2. Handle based on product type ===
            if order_item.is_supplier_product:
                # SUPPLIER PRODUCT: Split 93% supplier / 7% admin commission
                
                supplier = order_item.product.owner
                supplier_wallet = cls.get_supplier_wallet(supplier)
                
                item_supplier_amount = order_item.supplier_payout_amount  # 93,000 FRW
                item_commission = order_item.commission_amount  # 7,000 FRW
                
                # Add to Supplier Wallet
                supplier_wallet.add_balance(item_supplier_amount)
                supplier_transaction = WalletTransaction.objects.create(
                    wallet=supplier_wallet,
                    order=order,
                    order_item=order_item,
                    amount=item_supplier_amount,
                    transaction_type='credit',
                    category='supplier_payout',
                    status='completed',
                    description=f"Product sale from order #{order.order_number} - {order_item.product.name}",
                    metadata={
                        'product_name': order_item.product.name,
                        'quantity': order_item.quantity,
                        'base_price': float(order_item.base_price),
                        'commission_deducted': float(item_commission),
                        'commission_rate': 7
                    }
                )
                distributions.append({
                    'type': 'supplier_payout',
                    'recipient': supplier.email,
                    'amount': item_supplier_amount,
                    'transaction_id': str(supplier_transaction.id)
                })
                
                # Add to Admin Commission Wallet
                admin_wallet.add_balance(item_commission)
                commission_transaction = WalletTransaction.objects.create(
                    wallet=admin_wallet,
                    order=order,
                    order_item=order_item,
                    amount=item_commission,
                    transaction_type='credit',
                    category='commission',
                    status='completed',
                    description=f"Commission (7%) from order #{order.order_number} - {order_item.product.name}",
                    metadata={
                        'product_name': order_item.product.name,
                        'quantity': order_item.quantity,
                        'base_price': float(order_item.base_price),
                        'commission_rate': 7,
                        'supplier': supplier.email
                    }
                )
                distributions.append({
                    'type': 'commission',
                    'recipient': 'Admin',
                    'amount': item_commission,
                    'transaction_id': str(commission_transaction.id)
                })
                
                # Update CommissionEarning record
                CommissionEarning.objects.filter(order_item=order_item).update(
                    status='pending'
                )
                
                # Update SupplierPayout record
                SupplierPayout.objects.filter(order_item=order_item).update(
                    status='pending'
                )
                
            else:
                # ADMIN PRODUCT: 100% goes to admin (no commission)
                
                admin_revenue = order_item.base_price * order_item.quantity  # 100,000 FRW
                
                admin_wallet.add_balance(admin_revenue)
                admin_transaction = WalletTransaction.objects.create(
                    wallet=admin_wallet,
                    order=order,
                    order_item=order_item,
                    amount=admin_revenue,
                    transaction_type='credit',
                    category='product_sale',
                    status='completed',
                    description=f"Direct product sale from order #{order.order_number} - {order_item.product.name}",
                    metadata={
                        'product_name': order_item.product.name,
                        'quantity': order_item.quantity,
                        'base_price': float(order_item.base_price),
                        'product_type': 'admin_product'
                    }
                )
                distributions.append({
                    'type': 'product_sale',
                    'recipient': 'Admin',
                    'amount': admin_revenue,
                    'transaction_id': str(admin_transaction.id)
                })
        
        return {
            'success': True,
            'message': f'Successfully processed order #{order.order_number}',
            'distributions': distributions,
            'total_distributed': sum(d['amount'] for d in distributions)
        }
    
    # ============================================================
    # WITHDRAWAL MANAGEMENT
    # ============================================================
    
    @classmethod
    @transaction.atomic
    def create_withdrawal_request(
        cls, 
        user: User, 
        amount: Decimal, 
        phone_number: str = '',
        payment_method: str = 'mobile_money',
        bank_details: Optional[Dict] = None,
        notes: str = ''
    ) -> Dict[str, Any]:
        """
        Create a withdrawal request from user's wallet
        
        Args:
            user: User requesting withdrawal
            amount: Amount to withdraw
            phone_number: Mobile money number (for mobile money)
            payment_method: 'mobile_money' or 'bank_transfer'
            bank_details: Dict with bank_name, account_number, account_name
            notes: Optional notes
        
        Returns:
            Dict with success status and withdrawal details
        """
        
        # Determine wallet type based on user role
        if user.role == 'supplier':
            wallet_type = 'supplier'
        elif user.role == 'admin':
            wallet_type = 'admin'
        else:
            return {
                'success': False,
                'error': 'Only suppliers and admins can request withdrawals'
            }
        
        wallet = cls.get_or_create_wallet(user, wallet_type)
        
        # Validation
        if amount < cls.MINIMUM_WITHDRAWAL:
            return {
                'success': False,
                'error': f'Minimum withdrawal amount is {cls.MINIMUM_WITHDRAWAL:,.0f} FRW'
            }
        
        if amount > wallet.balance:
            return {
                'success': False,
                'error': f'Insufficient balance. Available: {wallet.balance:,.0f} FRW'
            }
        
        # Create withdrawal request
        withdrawal = WithdrawalRequest.objects.create(
            user=user,
            wallet=wallet,
            amount=amount,
            phone_number=phone_number,
            payment_method=payment_method,
            notes=notes,
            status='pending'
        )
        
        # Add bank details if provided
        if bank_details:
            withdrawal.bank_name = bank_details.get('bank_name', '')
            withdrawal.account_number = bank_details.get('account_number', '')
            withdrawal.account_name = bank_details.get('account_name', '')
            withdrawal.save()
        
        # Move amount to pending (reserved)
        wallet.balance -= amount
        wallet.pending_balance += amount
        wallet.save(update_fields=['balance', 'pending_balance', 'updated_at'])
        
        # Create wallet transaction for the pending withdrawal
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type='debit',
            category='withdrawal',
            status='pending',
            description=f"Withdrawal request of {amount:,.0f} FRW (Pending approval)",
            reference=f"WDR-{withdrawal.withdrawal_number}",
            metadata={
                'withdrawal_id': str(withdrawal.id),
                'status': 'pending'
            }
        )
        
        return {
            'success': True,
            'withdrawal': withdrawal,
            'withdrawal_id': str(withdrawal.id),
            'withdrawal_number': withdrawal.withdrawal_number,
            'amount': amount,
            'remaining_balance': wallet.balance
        }
    
    @classmethod
    @transaction.atomic
    def process_withdrawal(
        cls, 
        withdrawal_id: str, 
        admin_user: User, 
        approve: bool = True, 
        rejection_reason: str = ''
    ) -> Dict[str, Any]:
        """
        Admin approves or rejects a withdrawal request
        
        Args:
            withdrawal_id: UUID of the withdrawal request
            admin_user: Admin processing the request
            approve: True to approve, False to reject
            rejection_reason: Reason for rejection (if applicable)
        
        Returns:
            Dict with success status and message
        """
        
        withdrawal = WithdrawalRequest.objects.select_related('wallet', 'user').get(id=withdrawal_id)
        
        if withdrawal.status != 'pending':
            return {
                'success': False,
                'error': f'Withdrawal is already {withdrawal.status}'
            }
        
        if approve:
            # APPROVE: Mark as approved and ready for payout
            withdrawal.approve(admin_user)
            
            # Update wallet transaction
            WalletTransaction.objects.filter(
                wallet=withdrawal.wallet,
                reference__contains=withdrawal.withdrawal_number
            ).update(
                status='completed',
                metadata={
                    'withdrawal_id': str(withdrawal.id), 
                    'status': 'approved', 
                    'approved_by': admin_user.email
                }
            )
            
            return {
                'success': True,
                'message': f'Withdrawal request {withdrawal.withdrawal_number} approved. Ready for payout.',
                'withdrawal': withdrawal
            }
        else:
            # REJECT: Return money to wallet
            withdrawal.reject(admin_user, rejection_reason)
            
            # Return money to balance
            withdrawal.wallet.balance += withdrawal.amount
            withdrawal.wallet.pending_balance -= withdrawal.amount
            withdrawal.wallet.save(update_fields=['balance', 'pending_balance', 'updated_at'])
            
            # Update wallet transaction
            WalletTransaction.objects.filter(
                wallet=withdrawal.wallet,
                reference__contains=withdrawal.withdrawal_number
            ).update(
                status='failed',
                metadata={
                    'withdrawal_id': str(withdrawal.id), 
                    'status': 'rejected', 
                    'rejection_reason': rejection_reason,
                    'rejected_by': admin_user.email
                }
            )
            
            return {
                'success': True,
                'message': f'Withdrawal request {withdrawal.withdrawal_number} rejected. {rejection_reason}',
                'withdrawal': withdrawal
            }
    
    @classmethod
    @transaction.atomic
    def complete_withdrawal_payout(cls, withdrawal_id: str, transaction_reference: str = '') -> Dict[str, Any]:
        """
        Mark withdrawal as completed after successful API payout
        
        Args:
            withdrawal_id: UUID of the withdrawal request
            transaction_reference: Reference from payment provider
        
        Returns:
            Dict with success status
        """
        
        withdrawal = WithdrawalRequest.objects.select_related('wallet').get(id=withdrawal_id)
        
        if withdrawal.status != 'processing':
            return {
                'success': False,
                'error': f'Withdrawal must be in processing state. Current status: {withdrawal.status}'
            }
        
        withdrawal.mark_completed(transaction_reference)
        
        # Remove from pending balance
        withdrawal.wallet.pending_balance -= withdrawal.amount
        withdrawal.wallet.save(update_fields=['pending_balance', 'updated_at'])
        
        # Update wallet transaction
        WalletTransaction.objects.filter(
            wallet=withdrawal.wallet,
            reference__contains=withdrawal.withdrawal_number
        ).update(
            status='completed',
            metadata={
                'withdrawal_id': str(withdrawal.id), 
                'status': 'completed',
                'transaction_reference': transaction_reference
            }
        )
        
        return {
            'success': True,
            'message': f'Withdrawal {withdrawal.withdrawal_number} completed successfully'
        }
    
    # ============================================================
    # REPORTING & ANALYTICS
    # ============================================================
    
    @classmethod
    def get_admin_commission_summary(cls, admin_user: User) -> Dict[str, Any]:
        """
        Get comprehensive commission summary for admin
        
        Returns:
            Dict with total earned, available, withdrawn, pending requests
        """
        
        admin_wallet = cls.get_or_create_wallet(admin_user, 'admin')
        
        # Get total commission earned (from all time)
        total_earned = WalletTransaction.objects.filter(
            wallet=admin_wallet,
            category='commission',
            transaction_type='credit',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get total withdrawn
        total_withdrawn = WithdrawalRequest.objects.filter(
            user=admin_user,
            status__in=['completed', 'processing']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get pending withdrawal requests
        pending_requests = WithdrawalRequest.objects.filter(
            user=admin_user,
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'total_earned': total_earned,
            'available': admin_wallet.balance,
            'pending': admin_wallet.pending_balance,
            'withdrawn': total_withdrawn,
            'pending_requests': pending_requests,
            'wallet_balance': admin_wallet.balance,
        }
    
    @classmethod
    def get_supplier_earnings_summary(cls, supplier: User) -> Dict[str, Any]:
        """
        Get comprehensive earnings summary for a supplier
        
        Returns:
            Dict with total earned, available, pending payouts
        """
        
        supplier_wallet = cls.get_or_create_wallet(supplier, 'supplier')
        
        # Get total earned from all time
        total_earned = WalletTransaction.objects.filter(
            wallet=supplier_wallet,
            category='supplier_payout',
            transaction_type='credit',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get total withdrawn
        total_withdrawn = WithdrawalRequest.objects.filter(
            user=supplier,
            status__in=['completed', 'processing']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get pending withdrawal requests
        pending_requests = WithdrawalRequest.objects.filter(
            user=supplier,
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get total commission paid to admin
        total_commission_paid = WalletTransaction.objects.filter(
            wallet=supplier_wallet,
            category='commission',
            transaction_type='debit'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'total_earned': total_earned,
            'available': supplier_wallet.balance,
            'pending': supplier_wallet.pending_balance,
            'withdrawn': total_withdrawn,
            'pending_requests': pending_requests,
            'total_commission_paid': total_commission_paid,
            'wallet_balance': supplier_wallet.balance,
        }
    
    @classmethod
    def get_tax_summary(cls) -> Dict[str, Any]:
        """
        Get tax wallet summary for government VAT reporting
        
        Returns:
            Dict with total collected, available balance
        """
        
        tax_wallet = cls.get_tax_wallet()
        
        total_collected = WalletTransaction.objects.filter(
            wallet=tax_wallet,
            category='vat_collection',
            transaction_type='credit',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'total_vat_collected': total_collected,
            'available_balance': tax_wallet.balance,
            'pending': tax_wallet.pending_balance,
            'wallet_id': str(tax_wallet.id)
        }
    
    @classmethod
    def get_wallet_transactions(
        cls, 
        user: User, 
        wallet_type: str = 'supplier',
        limit: int = 50,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get wallet transaction history for a user
        
        Args:
            user: User object
            wallet_type: 'admin', 'supplier', or 'tax'
            limit: Number of transactions to return
            category: Filter by transaction category
        
        Returns:
            List of transaction dicts
        """
        
        wallet = cls.get_or_create_wallet(user, wallet_type)
        
        transactions = WalletTransaction.objects.filter(wallet=wallet)
        
        if category:
            transactions = transactions.filter(category=category)
        
        transactions = transactions.order_by('-created_at')[:limit]
        
        result = []
        for t in transactions:
            result.append({
                'id': str(t.id),
                'amount': t.amount,
                'type': t.get_transaction_type_display(),
                'category': t.get_category_display(),
                'description': t.description,
                'reference': t.reference,
                'created_at': t.created_at,
                'status': t.status,
                'order_number': t.order.order_number if t.order else None,
            })
        return result
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    @classmethod
    def get_available_balance(cls, user: User, wallet_type: str = 'supplier') -> Decimal:
        """Get available balance for withdrawal"""
        wallet = cls.get_or_create_wallet(user, wallet_type)
        return wallet.balance
    
    @classmethod
    def get_pending_balance(cls, user: User, wallet_type: str = 'supplier') -> Decimal:
        """Get pending balance (under withdrawal)"""
        wallet = cls.get_or_create_wallet(user, wallet_type)
        return wallet.pending_balance
    
    @classmethod
    def is_withdrawal_available(cls, user: User, amount: Decimal, wallet_type: str = 'supplier') -> Tuple[bool, str]:
        """
        Check if a withdrawal is possible
        
        Returns:
            Tuple of (is_available, message)
        """
        
        if amount < cls.MINIMUM_WITHDRAWAL:
            return False, f'Minimum withdrawal amount is {cls.MINIMUM_WITHDRAWAL:,.0f} FRW'
        
        wallet = cls.get_or_create_wallet(user, wallet_type)
        
        if amount > wallet.balance:
            return False, f'Insufficient balance. Available: {wallet.balance:,.0f} FRW'
        
        return True, 'Withdrawal available'