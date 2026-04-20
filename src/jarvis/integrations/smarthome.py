#!/usr/bin/env python3
"""
JARVIS Smart Home Integration
Control smart home devices using curl (no Python deps)
"""

import subprocess
import json
import os
import tempfile

class SmartHome:
    def __init__(self):
        self.homekit_enabled = False
        self.hue_bridge = None
        self.hue_api_key = None
        
        from jarvis.core.paths import smarthome_config_path

        config_file = str(smarthome_config_path())
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.hue_bridge = config.get('hue_bridge')
                self.hue_api_key = config.get('hue_api_key')
    
    def hue_lights(self):
        """Get all Hue lights"""
        if not self.hue_bridge or not self.hue_api_key:
            return "Hue not configured. Add bridge/key to config/smart-home.json under JARVIS_HOME."
        
        result = subprocess.run([
            'curl', '-s', 
            f"http://{self.hue_bridge}/api/{self.hue_api_key}/lights"
        ], capture_output=True, text=True, timeout=5)
        
        return result.stdout if result.stdout else "Error getting lights"
    
    def hue_set_light(self, light_id, on=True, bri=100):
        """Set Hue light on/off, brightness"""
        if not self.hue_bridge or not self.hue_api_key:
            return "Hue not configured"
        
        data = {"on": on, "bri": int(bri * 254 / 100)}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_file = f.name
        
        try:
            result = subprocess.run([
                'curl', '-s', '-X', 'PUT',
                f"http://{self.hue_bridge}/api/{self.hue_api_key}/lights/{light_id}/state",
                '-d', f'@{temp_file}'
            ], capture_output=True, text=True, timeout=5)
            return f"Light {light_id}: {'on' if on else 'off'} at {bri}%"
        finally:
            os.unlink(temp_file)
    
    def volume(self, level):
        """Set volume (0-100)"""
        level = max(0, min(100, level))
        result = subprocess.run([
            'osascript', '-e', f'set volume output volume {level}'
        ], capture_output=True)
        return f"Volume set to {level}%"
    
    def mute(self):
        """Mute volume"""
        result = subprocess.run([
            'osascript', '-e', 'set volume with output muted'
        ], capture_output=True)
        return "Muted"
    
    def wifi_status(self):
        """Get WiFi status"""
        result = subprocess.run([
            'networksetup', '-getairportnetwork', 'en0'
        ], capture_output=True, text=True)
        return result.stdout if result.stdout else "WiFi unavailable"
    
    def screen_brightness(self, level):
        """Set brightness (0-100) - requires brightness tool"""
        try:
            result = subprocess.run([
                'brightness', str(level / 100)
            ], capture_output=True)
            return f"Brightness set to {level}%"
        except:
            return "brightness tool not installed"
    
    def dim_display(self):
        """Dim display"""
        result = subprocess.run([
            'pmset', '-a', 'brightness', '10'
        ], capture_output=True)
        return "Display dimmed"


def test():
    """Test smart home"""
    sh = SmartHome()
    print("Volume:", sh.volume(50))
    print("WiFi:", sh.wifi_status().strip())


if __name__ == "__main__":
    test()