from user_agents import parse

class DeviceDetector:
    """Parse user agent to detect device type, OS, and browser"""
    
    @staticmethod
    def detect_device(user_agent_string):
        """Detect device information from user agent"""
        
        if not user_agent_string:
            return {
                'device_type': 'unknown',
                'os_type': 'unknown',
                'browser': 'Unknown',
                'browser_version': 'Unknown'
            }
        
        try:
            user_agent = parse(user_agent_string)
            
            # Detect device type
            if user_agent.is_pc:
                device_type = 'pc'
            elif user_agent.is_smartphone:
                device_type = 'smartphone'
            elif user_agent.is_tablet:
                device_type = 'tablet'
            else:
                device_type = 'unknown'
            
            # Detect OS
            os_string = user_agent.os.family.lower()
            if 'windows' in os_string:
                os_type = 'windows'
            elif 'mac' in os_string:
                os_type = 'macos'
            elif 'linux' in os_string:
                os_type = 'linux'
            elif 'android' in os_string:
                os_type = 'android'
            elif 'ios' in os_string or 'iphone' in os_string or 'ipad' in os_string:
                os_type = 'ios'
            else:
                os_type = 'unknown'
            
            return {
                'device_type': device_type,
                'os_type': os_type,
                'browser': user_agent.browser.family,
                'browser_version': user_agent.browser.version_string
            }
            
        except Exception:
            return {
                'device_type': 'unknown',
                'os_type': 'unknown',
                'browser': 'Unknown',
                'browser_version': 'Unknown'
            }