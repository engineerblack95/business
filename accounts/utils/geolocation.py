import requests
import json
import socket
from django.conf import settings


class GeoLocationService:
    """Get location information from IP address using multiple fallback services"""
    
    # Cache for IP lookups to avoid rate limiting
    _cache = {}
    
    @classmethod
    def get_client_ip(cls, request):
        """
        Get real client IP address even when behind proxy (like Render, Heroku, etc.)
        """
        # Check for proxy forwarded IPs
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Get the first IP in the list (client IP)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Handle localhost
        if ip in ['127.0.0.1', 'localhost']:
            # Try to get actual local network IP for better development experience
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
            except:
                pass
        
        return ip
    
    @classmethod
    def get_location_from_ip(cls, ip_address):
        """
        Get location details from IP address using multiple free APIs
        Returns dict with country, city, region, lat, lon
        """
        
        # Check cache first
        if ip_address in cls._cache:
            return cls._cache[ip_address]
        
        # Default response for localhost
        if ip_address in ['127.0.0.1', 'localhost']:
            return {
                'country': 'Local',
                'city': 'Development',
                'region': 'Local',
                'lat': None,
                'lon': None,
                'success': True
            }
        
        # Try multiple APIs in order
        apis = [
            cls._get_location_ipapi,
            cls._get_location_ipwhois,
            cls._get_location_ipinfo,
        ]
        
        for api in apis:
            result = api(ip_address)
            if result and result.get('success'):
                cls._cache[ip_address] = result
                return result
        
        # Fallback if all APIs fail
        return {
            'country': 'Unknown',
            'city': 'Unknown',
            'region': 'Unknown',
            'lat': None,
            'lon': None,
            'success': False
        }
    
    @classmethod
    def _get_location_ipapi(cls, ip_address):
        """
        Use ip-api.com (free, no API key required)
        Limits: 45 requests per minute from a single IP
        """
        try:
            url = f"http://ip-api.com/json/{ip_address}?fields=status,country,city,regionName,lat,lon"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country', 'Unknown'),
                        'city': data.get('city', 'Unknown'),
                        'region': data.get('regionName', ''),
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                        'success': True
                    }
        except Exception as e:
            print(f"ip-api.com error: {e}")
        return None
    
    @classmethod
    def _get_location_ipwhois(cls, ip_address):
        """
        Use ipwhois.io (free, no API key required)
        Limits: 10,000 requests per month
        """
        try:
            url = f"http://ipwhois.io/json/{ip_address}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # Check if response is valid (not error)
                if data.get('success') != False and 'country' in data:
                    return {
                        'country': data.get('country', 'Unknown'),
                        'city': data.get('city', 'Unknown'),
                        'region': data.get('region', ''),
                        'lat': data.get('latitude'),
                        'lon': data.get('longitude'),
                        'success': True
                    }
        except Exception as e:
            print(f"ipwhois.io error: {e}")
        return None
    
    @classmethod
    def _get_location_ipinfo(cls, ip_address):
        """
        Use ipinfo.io (free, no API key required for limited usage)
        Limits: 50,000 requests per month
        """
        try:
            url = f"https://ipinfo.io/{ip_address}/json"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # Check if response is valid (no 'bogon' for private IPs)
                if 'bogon' not in data:
                    location = data.get('loc', '').split(',')
                    lat = float(location[0]) if len(location) > 0 else None
                    lon = float(location[1]) if len(location) > 1 else None
                    return {
                        'country': data.get('country', 'Unknown'),
                        'city': data.get('city', 'Unknown'),
                        'region': data.get('region', ''),
                        'lat': lat,
                        'lon': lon,
                        'success': True
                    }
        except Exception as e:
            print(f"ipinfo.io error: {e}")
        return None
    
    @classmethod
    def clear_cache(cls):
        """Clear the IP location cache"""
        cls._cache = {}