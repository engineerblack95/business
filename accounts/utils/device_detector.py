from user_agents import parse
import re


class DeviceDetector:
    """Parse user agent to detect device type, OS, and browser accurately"""
    
    @staticmethod
    def detect_device(user_agent_string):
        """Detect device information from user agent"""
        
        if not user_agent_string:
            return {
                'device_type': 'unknown',
                'device_display': 'Unknown Device',
                'os_type': 'unknown',
                'os_display': 'Unknown OS',
                'browser': 'Unknown',
                'browser_version': 'Unknown',
                'browser_display': 'Unknown Browser',
                'device_brand': 'Unknown',
                'device_model': 'Unknown'
            }
        
        try:
            user_agent = parse(user_agent_string)
            
            # Detect device type with display names
            if user_agent.is_pc:
                device_type = 'pc'
                device_display = 'Computer'
            elif user_agent.is_smartphone:
                device_type = 'smartphone'
                device_display = 'Smartphone'
            elif user_agent.is_tablet:
                device_type = 'tablet'
                device_display = 'Tablet'
            elif user_agent.is_bot:
                device_type = 'bot'
                device_display = 'Bot/Crawler'
            else:
                device_type = 'unknown'
                device_display = 'Unknown Device'
            
            # Detect OS with detailed display names
            os_family = user_agent.os.family
            os_version = user_agent.os.version_string
            
            if 'windows' in os_family.lower():
                os_type = 'windows'
                # Extract Windows version
                if '10' in os_version:
                    os_display = f'Windows 10'
                elif '11' in os_version:
                    os_display = f'Windows 11'
                elif '8' in os_version:
                    os_display = f'Windows {os_version}'
                elif '7' in os_version:
                    os_display = 'Windows 7'
                else:
                    os_display = f'Windows {os_version}' if os_version else 'Windows'
            
            elif 'mac' in os_family.lower() or 'ios' in os_family.lower():
                os_type = 'macos'
                if 'iphone' in os_family.lower():
                    os_display = f'iOS {os_version}' if os_version else 'iOS'
                elif 'ipad' in os_family.lower():
                    os_display = f'iPadOS {os_version}' if os_version else 'iPadOS'
                else:
                    os_display = f'macOS {os_version}' if os_version else 'macOS'
            
            elif 'linux' in os_family.lower():
                os_type = 'linux'
                os_display = 'Linux'
            
            elif 'android' in os_family.lower():
                os_type = 'android'
                # Extract Android version
                if os_version:
                    os_display = f'Android {os_version}'
                else:
                    os_display = 'Android'
            
            elif 'chrome os' in os_family.lower():
                os_type = 'chromeos'
                os_display = 'Chrome OS'
            
            else:
                os_type = 'unknown'
                os_display = os_family if os_family else 'Unknown OS'
            
            # Detect browser with display names
            browser_family = user_agent.browser.family
            browser_version = user_agent.browser.version_string
            
            # Map browser families to display names
            browser_lower = browser_family.lower()
            if 'chrome' in browser_lower and 'edge' not in browser_lower:
                browser_display = 'Google Chrome'
            elif 'firefox' in browser_lower:
                browser_display = 'Mozilla Firefox'
            elif 'safari' in browser_lower and 'chrome' not in browser_lower:
                browser_display = 'Safari'
            elif 'edge' in browser_lower:
                browser_display = 'Microsoft Edge'
            elif 'opera' in browser_lower:
                browser_display = 'Opera'
            elif 'ie' in browser_lower or 'internet explorer' in browser_lower:
                browser_display = 'Internet Explorer'
            elif 'brave' in browser_lower:
                browser_display = 'Brave'
            else:
                browser_display = browser_family
            
            # Get device brand and model if available
            device_brand = user_agent.device.brand or 'Unknown'
            device_model = user_agent.device.model or 'Unknown'
            
            return {
                'device_type': device_type,
                'device_display': device_display,
                'os_type': os_type,
                'os_display': os_display,
                'browser': browser_family,
                'browser_version': browser_version,
                'browser_display': browser_display,
                'device_brand': device_brand,
                'device_model': device_model
            }
            
        except Exception as e:
            print(f"Device detection error: {e}")
            return {
                'device_type': 'unknown',
                'device_display': 'Unknown Device',
                'os_type': 'unknown',
                'os_display': 'Unknown OS',
                'browser': 'Unknown',
                'browser_version': 'Unknown',
                'browser_display': 'Unknown Browser',
                'device_brand': 'Unknown',
                'device_model': 'Unknown'
            }
    
    @staticmethod
    def get_device_icon(device_type):
        """Return Font Awesome icon class for device type"""
        icons = {
            'pc': 'fa-desktop',
            'smartphone': 'fa-mobile-alt',
            'tablet': 'fa-tablet-alt',
            'bot': 'fa-robot',
            'unknown': 'fa-question-circle'
        }
        return icons.get(device_type, 'fa-laptop')
    
    @staticmethod
    def get_os_icon(os_type):
        """Return Font Awesome icon class for OS type"""
        icons = {
            'windows': 'fa-windows',
            'macos': 'fa-apple',
            'linux': 'fa-linux',
            'android': 'fa-android',
            'ios': 'fa-mobile',
            'chromeos': 'fa-chrome',
            'unknown': 'fa-question-circle'
        }
        return icons.get(os_type, 'fa-microchip')
    
    @staticmethod
    def get_browser_icon(browser_name):
        """Return Font Awesome icon class for browser"""
        browser_lower = browser_name.lower()
        if 'chrome' in browser_lower:
            return 'fa-chrome'
        elif 'firefox' in browser_lower:
            return 'fa-firefox'
        elif 'safari' in browser_lower:
            return 'fa-safari'
        elif 'edge' in browser_lower:
            return 'fa-edge'
        elif 'opera' in browser_lower:
            return 'fa-opera'
        elif 'ie' in browser_lower or 'internet explorer' in browser_lower:
            return 'fa-internet-explorer'
        else:
            return 'fa-globe'