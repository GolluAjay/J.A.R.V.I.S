#!/usr/bin/env python3
"""
JARVIS Automation System
Scheduled tasks and event triggers (no external deps)
"""

import os
import json
import time
import subprocess
import threading
from datetime import datetime

from jarvis.core.paths import automation_config_path
from jarvis.core.shell_policy import REFUSAL_MESSAGE, shell_requires_consent

class Automation:
    def __init__(self, config_file=None):
        if config_file:
            self.config_file = config_file
        else:
            self.config_file = str(automation_config_path())
        
        self.load_config()
        self.running = False
    
    def load_config(self):
        """Load automation config"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {'triggers': []}
            self.save_config()
    
    def save_config(self):
        """Save automation config"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def add_trigger(self, name, schedule, action):
        """Add an automation trigger"""
        trigger = {
            'name': name,
            'schedule': schedule,  # time like "08:00" or "interval:seconds"
            'action': action,
            'enabled': True,
            'last_run': None
        }
        self.config['triggers'].append(trigger)
        self.save_config()
        return f"Added: {name}"
    
    def remove_trigger(self, name):
        """Remove a trigger"""
        triggers = self.config['triggers']
        self.config['triggers'] = [t for t in triggers if t['name'] != name]
        self.save_config()
        return f"Removed: {name}"
    
    def list_triggers(self):
        """List all triggers"""
        if not self.config['triggers']:
            return "No triggers"
        
        lines = []
        for t in self.config['triggers']:
            status = "✓" if t.get('enabled') else "✗"
            lines.append(f"{status} {t['name']} @ {t['schedule']}")
        return '\n'.join(lines)
    
    def execute_action(self, action):
        """Execute an action"""
        if action.startswith('say:'):
            text = action[4:]
            subprocess.run(['say', text])
            return f"Spoke: {text}"
        
        elif action.startswith('notify:'):
            text = action[7:]
            subprocess.run(['osascript', '-e', f'display notification "{text}"'])
            return f"Notified: {text}"
        
        elif action.startswith('command:'):
            cmd = action[8:]
            if shell_requires_consent(cmd):
                return REFUSAL_MESSAGE
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout[:100] if result.returncode == 0 else "Error"
        
        return "Unknown action"
    
    def check_trigger(self, schedule):
        """Check if trigger should fire"""
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        
        if schedule == time_str:
            return True
        return False
    
    def start(self):
        """Start automation daemon (runs in background)"""
        self.running = True
        
        def run_loop():
            while self.running:
                for t in self.config['triggers']:
                    if not t.get('enabled', True):
                        continue
                    if self.check_trigger(t['schedule']):
                        last = t.get('last_run')
                        if last:
                            last_time = datetime.fromisoformat(last)
                            if (datetime.now() - last_time).seconds < 60:
                                continue
                        print(f"⚡ Trigger: {t['name']}")
                        self.execute_action(t['action'])
                        t['last_run'] = datetime.now().isoformat()
                        self.save_config()
                time.sleep(30)
        
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        return "Automation started"
    
    def stop(self):
        """Stop automation"""
        self.running = False
        return "Automation stopped"


def test():
    """Test automation"""
    auto = Automation()
    
    # Add sample
    auto.add_trigger('test_alarm', '23:59', 'say:Test complete.')
    
    print("Triggers:", auto.list_triggers())
    print("Action:", auto.execute_action('say:Test working.'))


if __name__ == "__main__":
    test()