import requests
import json
from django.conf import settings

class GeoLocationService:
    """Get location information from IP address"""
    
    @staticmethod
    def get_location_from_ip(ip_address):
        """
        Get location details from IP address using free ip-api.com
        Returns dict with country, city, lat, lon
        """
        if ip_address == '127.0.0.1':
            # Default location for localhost
            return {
                'country': 'Localhost',
                'city': 'Development',
                'lat': None,
                'lon': None,
                'success': True
            }
        
        try:
            url = f"http://ip-api.com/json/{ip_address}?fields=status,country,city,lat,lon"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country', 'Unknown'),
                        'city': data.get('city', 'Unknown'),
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                        'success': True
                    }
            
            return {
                'country': 'Unknown',
                'city': 'Unknown',
                'lat': None,
                'lon': None,
                'success': False
            }
            
        except requests.RequestException:
            return {
                'country': 'Unknown',
                'city': 'Unknown',
                'lat': None,
                'lon': None,
                'success': False
            }