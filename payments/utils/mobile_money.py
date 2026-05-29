import requests
import json
import hashlib
import hmac
import base64
import time
from decimal import Decimal
from django.conf import settings
from datetime import datetime
import secrets

class MobileMoneyProcessor:
    """Base class for mobile money processing"""
    
    def __init__(self, provider='mtn'):
        self.provider = provider
        self.sandbox_mode = getattr(settings, 'PAYMENT_SANDBOX_MODE', True)
        
    def generate_transaction_id(self):
        """Generate unique transaction ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random = secrets.token_hex(4).upper()
        return f"{self.provider.upper()}-{timestamp}-{random}"
    
    def simulate_payment(self, phone_number, amount):
        """
        Simulate payment for development
        Returns (success, transaction_id, message)
        """
        # Simulate processing delay
        import time as timer
        timer.sleep(2)
        
        # Always succeed in simulation
        transaction_id = self.generate_transaction_id()
        
        # Simulate random failure (10% chance for testing)
        # import random
        # if random.random() < 0.1:
        #     return False, None, "Simulated payment failure"
        
        return True, transaction_id, "Payment processed successfully (simulated)"


class MTNMobileMoney(MobileMoneyProcessor):
    """MTN Mobile Money API integration"""
    
    def __init__(self):
        super().__init__(provider='mtn')
        self.api_user = getattr(settings, 'MTN_API_USER', '')
        self.api_key = getattr(settings, 'MTN_API_KEY', '')
        self.subscription_key = getattr(settings, 'MTN_SUBSCRIPTION_KEY', '')
        self.target_environment = 'sandbox' if self.sandbox_mode else 'production'
        
    def get_access_token(self):
        """Get OAuth access token from MTN"""
        if self.sandbox_mode:
            # Return mock token for sandbox
            return "mock_access_token_12345"
        
        # Production implementation
        url = "https://sandbox.momodeveloper.mtn.com/collection/token/"
        auth = base64.b64encode(f"{self.api_user}:{self.api_key}".encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth}',
            'Ocp-Apim-Subscription-Key': self.subscription_key,
        }
        
        try:
            response = requests.post(url, headers=headers)
            if response.status_code == 200:
                return response.json().get('access_token')
        except Exception as e:
            print(f"MTN token error: {e}")
        
        return None
    
    def initiate_payment(self, phone_number, amount, transaction_id, callback_url=None):
        """
        Initiate MTN Mobile Money payment
        Returns (success, transaction_id, message)
        """
        if self.sandbox_mode:
            # Sandbox simulation
            return self.simulate_payment(phone_number, amount)
        
        # Production implementation
        access_token = self.get_access_token()
        if not access_token:
            return False, None, "Failed to authenticate with MTN"
        
        url = "https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'X-Reference-Id': transaction_id,
            'X-Target-Environment': self.target_environment,
            'Ocp-Apim-Subscription-Key': self.subscription_key,
            'Content-Type': 'application/json',
        }
        
        payload = {
            'amount': str(amount),
            'currency': 'RWF',
            'externalId': transaction_id,
            'payer': {
                'partyIdType': 'MSISDN',
                'partyId': phone_number
            },
            'payerMessage': f'Payment for order',
            'payeeNote': f'HerosTechnology order payment'
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 202:
                return True, transaction_id, "Payment initiated successfully"
            else:
                return False, None, f"Payment initiation failed: {response.text}"
                
        except Exception as e:
            return False, None, f"Error: {str(e)}"
    
    def check_payment_status(self, transaction_id):
        """Check payment status"""
        if self.sandbox_mode:
            # Return success for sandbox
            return 'SUCCESSFUL'
        
        access_token = self.get_access_token()
        if not access_token:
            return 'FAILED'
        
        url = f"https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay/{transaction_id}"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'X-Target-Environment': self.target_environment,
            'Ocp-Apim-Subscription-Key': self.subscription_key,
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json().get('status', 'FAILED')
        except Exception as e:
            print(f"Status check error: {e}")
        
        return 'FAILED'


class AirtelMoney(MobileMoneyProcessor):
    """Airtel Money API integration"""
    
    def __init__(self):
        super().__init__(provider='airtel')
        self.client_id = getattr(settings, 'AIRTEL_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'AIRTEL_CLIENT_SECRET', '')
        self.api_key = getattr(settings, 'AIRTEL_API_KEY', '')
        
    def get_access_token(self):
        """Get access token from Airtel"""
        if self.sandbox_mode:
            return "mock_airtel_token"
        
        # Production implementation
        url = "https://openapi.airtel.africa/auth/oauth2/token"
        
        headers = {
            'Content-Type': 'application/json',
            'X-Country': 'RW',
            'X-Currency': 'RWF',
        }
        
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json().get('access_token')
        except Exception as e:
            print(f"Airtel token error: {e}")
        
        return None
    
    def initiate_payment(self, phone_number, amount, transaction_id, callback_url=None):
        """Initiate Airtel Money payment"""
        if self.sandbox_mode:
            return self.simulate_payment(phone_number, amount)
        
        # Production implementation
        access_token = self.get_access_token()
        if not access_token:
            return False, None, "Failed to authenticate with Airtel"
        
        # Airtel API implementation
        # ... similar to MTN implementation
        
        return True, transaction_id, "Payment initiated successfully"