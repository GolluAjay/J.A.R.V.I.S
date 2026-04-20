#!/usr/bin/env python3
"""
JARVIS Web UI - Advanced Orchestrator Interface
"""

import http.server
import socketserver
import os
import json
import subprocess
import socket
import urllib.parse
from datetime import datetime

from jarvis.core.paths import html_index_path
from jarvis.core.shell_policy import REFUSAL_MESSAGE, shell_requires_consent

HTML_FILE = str(html_index_path())

_PRIVILEGED_ACTIONS = frozenset({"reboot", "shutdown", "empty_trash", "clear_cache"})

def get_port(default=8080):
    for port in range(default, default + 10):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("", port))
            s.close()
            return port
        except OSError:
            continue
    return default

PORT = get_port()

# === ORCHESTRATOR FUNCTIONS ===

def get_system_stats():
    """Get system statistics"""
    stats = {}
    
    # CPU - using top
    try:
        result = subprocess.run(
            ['top', '-l', '1', '-n', '0'],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split('\n'):
            if 'CPU usage:' in line:
                # Parse: CPU usage: 45.12% user, 8.34% sys, 46.54% idle
                parts = line.split('%')
                user = parts[0].split()[-1]
                sys_usage = parts[1].split()[0]
                idle = parts[2].split()[0]
                stats['cpu'] = f"{float(user) + float(sys_usage):.1f}%"
                break
        else:
            stats['cpu'] = "N/A"
    except Exception:
        stats['cpu'] = "N/A"
    
    # Memory
    try:
        result = subprocess.run(
            ['vm_stat'],
            capture_output=True, text=True, timeout=5
        )
        page_size = 4096
        mem_info = {}
        for line in result.stdout.split('\n'):
            if 'Pages active:' in line:
                mem_info['active'] = int(line.split()[-1].replace('.', '')) * page_size
            elif 'Pages inactive:' in line:
                mem_info['inactive'] = int(line.split()[-1].replace('.', '')) * page_size
            elif 'Pages wired down:' in line:
                mem_info['wired'] = int(line.split()[-1].replace('.', '')) * page_size
            elif 'Pages free:' in line:
                mem_info['free'] = int(line.split()[-1].replace('.', '')) * page_size
            elif 'Pages speculative:' in line:
                mem_info['speculative'] = int(line.split()[-1].replace('.', '')) * page_size
        
        # Get actual total from sysctl
        total_result = subprocess.run(
            ['sysctl', '-n', 'hw.memsize'],
            capture_output=True, text=True, timeout=5
        )
        total = int(total_result.stdout.strip()) if total_result.returncode == 0 else 0
        
        if total > 0:
            used = mem_info.get('active', 0) + mem_info.get('wired', 0)
            used_pct = (used / total * 100)
            stats['memory'] = f"Used: {used_pct:.1f}% ({used//1024//1024}MB / {total//1024//1024}MB)"
        else:
            stats['memory'] = "N/A"
    except Exception:
        stats['memory'] = "N/A"
    
    # Disk
    try:
        result = subprocess.run(
            ['df', '-h', '/'],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            # parts: Filesystem, Size, Used, Avail, Capacity%, Mounted
            stats['disk'] = f"{parts[4]} ({parts[2]} used / {parts[1]} total)"
        else:
            stats['disk'] = "N/A"
    except Exception:
        stats['disk'] = "N/A"
    
    # Uptime
    try:
        result = subprocess.run(
            ['uptime'],
            capture_output=True, text=True, timeout=5
        )
        stats['uptime'] = result.stdout.strip().split('up ')[-1].split(',')[0]
    except Exception:
        stats['uptime'] = "N/A"
    
    return stats

def get_top_processes(limit=5):
    """Get top processes by CPU usage"""
    processes = []
    try:
        result = subprocess.run(
            ['ps', 'aux', '-r'],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')[1:limit+1]
        for line in lines:
            parts = line.split()
            if len(parts) >= 11:
                processes.append({
                    'pid': parts[1],
                    'cpu': parts[2],
                    'mem': parts[3],
                    'name': ' '.join(parts[10:])
                })
    except Exception:
        pass
    return processes

def list_processes(search=""):
    """List all processes"""
    processes = []
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')[1:]
        for line in lines:
            parts = line.split()
            if len(parts) >= 11:
                name = ' '.join(parts[10:])
                if not search or search.lower() in name.lower():
                    processes.append({
                        'pid': parts[1],
                        'cpu': parts[2],
                        'mem': parts[3],
                        'name': name
                    })
    except Exception:
        pass
    return processes[:50]

def kill_process(pid):
    """Kill a process by PID"""
    try:
        result = subprocess.run(
            ['kill', pid],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def run_terminal_command(command, confirmed=False):
    """Run a shell command (privileged patterns require confirm=True)."""
    if not confirmed and shell_requires_consent(command):
        return (
            f"{REFUSAL_MESSAGE} "
            'Send {"command": "<cmd>", "confirm": true} after you approve once in the UI.'
        )
    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True, timeout=30
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {str(e)}"

def get_docker_status():
    """Get Docker status"""
    try:
        # Check if Docker is running
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return "Docker is not running"
        
        # Get container list
        result = subprocess.run(
            ['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}|{{.Image}}'],
            capture_output=True, text=True, timeout=5
        )
        
        output = "CONTAINERS:\n"
        if result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                parts = line.split('|')
                if len(parts) >= 3:
                    output += f"  • {parts[0]} ({parts[2]}) - {parts[1]}\n"
        else:
            output += "  No containers\n"
        
        # Get images
        result = subprocess.run(
            ['docker', 'images', '--format', '{{.Repository}}|{{.Tag}}|{{.Size}}'],
            capture_output=True, text=True, timeout=5
        )
        
        output += "\nIMAGES:\n"
        if result.stdout.strip():
            for line in result.stdout.strip().split('\n')[:5]:
                parts = line.split('|')
                if len(parts) >= 3:
                    output += f"  • {parts[0]}:{parts[1]} ({parts[2]})\n"
        else:
            output += "  No images\n"
        
        return output
    except FileNotFoundError:
        return "Docker not installed"
    except Exception as e:
        return f"Docker error: {str(e)}"

def execute_action(action, confirmed=False):
    """Execute system actions"""
    actions = {
        'reboot': 'sudo shutdown -r now',
        'shutdown': 'sudo shutdown -h now',
        'sleep': 'pmset sleepnow',
        'lock': '/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend',
        'empty_trash': 'rm -rf ~/.Trash/*',
        'clear_cache': 'rm -rf ~/Library/Caches/*',
        'cpu': 'top -l 1 -n 0 | grep -E "CPU|Processes"',
        'memory': 'vm_stat',
        'disk': 'df -h /',
        'battery': 'pmset -g batt',
        'docker': 'docker ps -a 2>/dev/null || echo "Docker not running"',
    }

    if action in _PRIVILEGED_ACTIONS and not confirmed:
        return (
            "This action is privileged or destructive, sir. "
            'Retry with {"action": "<name>", "confirm": true} after you approve once.'
        )

    if action in actions:
        inner = actions[action]
        if action in _PRIVILEGED_ACTIONS:
            return run_terminal_command(inner, confirmed=True)
        return run_terminal_command(inner, confirmed=False)
    return f"Unknown action: {action}"

# === HTTP HANDLER ===

class JARVISHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/chat':
            self.handle_chat()
        elif self.path == '/api/terminal':
            self.handle_terminal()
        elif self.path == '/api/action':
            self.handle_action()
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path == '/':
            # Serve index.html for root
            self.path = '/index.html'
            super().do_GET()
        elif self.path == '/api/system':
            self.handle_system()
        elif self.path == '/api/processes':
            self.handle_processes()
        elif self.path == '/api/docker':
            self.handle_docker()
        elif self.path.startswith('/api/'):
            self.send_error(404)
        else:
            # Serve static files
            super().do_GET()
    
    def handle_chat(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        message = json.loads(post_data.decode())['message']
        
        result = self.process_message(message)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'response': result}).encode())
    
    def handle_system(self):
        stats = get_system_stats()
        top_procs = get_top_processes()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            'stats': stats,
            'top_procs': top_procs,
            'timestamp': datetime.now().isoformat()
        }).encode())
    
    def handle_processes(self):
        search = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        ).get('search', [''])[0]
        
        pid = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        ).get('pid', [''])[0]
        
        if pid:
            success = kill_process(pid)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': success}).encode())
        else:
            processes = list_processes(search)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'processes': processes}).encode())
    
    def handle_docker(self):
        output = get_docker_status()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'output': output}).encode())
    
    def handle_terminal(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())
        command = data.get('command', '')
        confirmed = bool(data.get('confirm'))

        result = run_terminal_command(command, confirmed=confirmed)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'result': result}).encode())
    
    def handle_action(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode())
        action = data.get('action', '')
        confirmed = bool(data.get('confirm'))

        result = execute_action(action, confirmed=confirmed)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'result': result}).encode())
    
    def process_message(self, message):
        """Process message through JARVIS"""
        prompt = f"""You are JARVIS, Tony Stark's AI. Be helpful, brief, witty. 
Keep responses short. Call user 'sir'.

User: {message}

JARVIS:"""
        
        req_data = {
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False
        }
        
        try:
            result = subprocess.run(
                ['curl', '-s', 'http://localhost:11434/api/generate',
                 '-H', 'Content-Type: application/json',
                 '-d', json.dumps(req_data)],
                capture_output=True, text=True, timeout=30
            )
            
            data = json.loads(result.stdout)
            return data.get('response', 'I apologize, sir. Something went wrong.')
        except Exception:
            return "I'm having trouble thinking right now, sir."

    def log_message(self, format, *args):
        print(f"[JARVIS] {args[0]}")

# === SERVE HTML ===

def serve_html():
    """Write and serve index.html"""
    if os.path.exists(HTML_FILE):
        os.chdir(os.path.dirname(HTML_FILE))
        return
    
    # Fallback: create basic HTML
    html = '''<!DOCTYPE html>
<html>
<head><title>JARVIS</title></head>
<body>
<h1>JARVIS</h1>
<p>Serving from: ''' + HTML_FILE + '''
</body>
'''
    os.makedirs(os.path.dirname(HTML_FILE), exist_ok=True)
    with open(HTML_FILE, 'w') as f:
        f.write(html)
    os.chdir(os.path.dirname(HTML_FILE))

def main():
    serve_html()

    print(f"""
╔═══════════════════════════════════════════════════════╗
║     🤖 JARVIS Advanced Orchestrator                   ║
╠═══════════════════════════════════════════════════════╣
║                                                       ║
║  Opening browser at: http://localhost:{PORT}          ║
║                                                       ║
║  API Endpoints:                                       ║
║    GET  /api/system   - System stats                  ║
║    GET  /api/processes - List processes               ║  
║    GET  /api/docker   - Docker status                 ║
║    POST /api/terminal - Run command                   ║
║    POST /api/action  - System actions                 ║
║    POST /chat        - AI chat                        ║
║                                                       ║
║  Press Ctrl+C to stop.                                ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
""")
    
    os.chdir(os.path.dirname(HTML_FILE))
    with socketserver.TCPServer(("", PORT), JARVISHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
