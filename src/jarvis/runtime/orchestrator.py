#!/usr/bin/env python3
"""
JARVIS Advanced Orchestrator
Pure shell-based system management (no external deps)
"""

import os
import subprocess
import socket
from datetime import datetime

from jarvis.core.shell_policy import REFUSAL_MESSAGE, shell_requires_consent


class Orchestrator:
    def __init__(self, cwd=None):
        self.name = "JARVIS"
        self.start_time = datetime.now()
        self.cwd = cwd or os.getcwd()
    
    def set_cwd(self, path):
        """Update the working directory"""
        if os.path.isdir(path):
            self.cwd = path
            return True
        return False
    
    def _run_raw(self, cmd):
        """Run shell command in CWD (no consent gate; internal use)."""
        try:
            result = subprocess.run(
                cmd, shell=True,
                cwd=self.cwd,
                capture_output=True, text=True, timeout=10
            )
            return result.stdout if result.returncode == 0 else f"Error: {result.stderr[:100]}"
        except Exception as e:
            return f"Execution error: {str(e)}"

    def run_cmd(self, cmd):
        """Run shell command safely in the current CWD (refuses privileged strings)."""
        if shell_requires_consent(cmd):
            return REFUSAL_MESSAGE
        return self._run_raw(cmd)
    
    # ===== SYSTEM MONITOR =====
    def get_system_stats(self):
        """Get system stats using shell"""
        # CPU
        top = self._run_raw("top -l 1 -n 0 | grep 'CPU usage' | awk '{print $3}' | tr -d '%'")
        cpu = top.strip() or "N/A"
        
        # Memory
        mem = self._run_raw("vm_stat | head -8")
        
        # Disk
        disk = self._run_raw("df -h / | tail -1 | awk '{print $5, $3, $2}'")
        
        # Network
        net = self._run_raw("netstat -ib | head -10")
        
        # Uptime
        uptime = self._run_raw("uptime")
        
        return {
            "cpu": f"{cpu}%",
            "memory": mem.replace('\n', ' ')[:100],
            "disk": disk,
            "uptime": uptime.strip(),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    
    def get_top_processes(self, limit=10):
        """Get top processes"""
        output = self._run_raw(f"ps aux -r | head -{limit + 1}")
        processes = []
        for line in output.split('\n')[1:limit+1]:
            parts = line.split()
            if len(parts) > 9:
                processes.append({
                    'pid': parts[1],
                    'cpu': parts[2],
                    'mem': parts[3],
                    'name': ' '.join(parts[10:])[:30]
                })
        return processes
    
    def get_cpu_per_core(self):
        """Get CPU per core"""
        return self._run_raw("sysctl -n machdep.cpu.brand_string")
    
    # ===== PROCESS MANAGEMENT =====
    def list_processes(self, search=None):
        """List processes"""
        cmd = "ps -eo pid,pcpu,pmem,comm | head -30"
        if search:
            cmd = f"ps -eo pid,pcpu,pmem,comm | grep -i {search} | head -20"
        
        output = self.run_cmd(cmd)
        processes = []
        for line in output.split('\n')[1:]:
            parts = line.split(None, 3)
            if len(parts) >= 4:
                processes.append({
                    'pid': parts[0],
                    'cpu': parts[1],
                    'mem': parts[2],
                    'name': parts[3][:40]
                })
        return processes
    
    def kill_process(self, pid):
        """Kill process"""
        return self.run_cmd(f"kill {pid}")
    
    def get_process_tree(self):
        """Get process tree"""
        return self._run_raw("ps -ax -o pid,ppid,comm | head -20")
    
    # ===== FILE OPERATIONS =====
    def list_directory(self, path="~", show_hidden=False):
        """List directory"""
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return f"Path not found: {path}"
        
        cmd = f"ls -lh{'a' if show_hidden else ''} {path} | head -30"
        return self.run_cmd(cmd)
    
    def file_info(self, path):
        """Get file info"""
        path = os.path.expanduser(path)
        return self.run_cmd(f"stat {path}")
    
    def read_file(self, path, lines=20):
        """Read file"""
        path = os.path.expanduser(path)
        return self.run_cmd(f"head -{lines} {path}")
    
    # ===== NETWORK OPERATIONS =====
    def get_network_info(self):
        """Get network interfaces"""
        return self._run_raw("ifconfig | grep -E '^[a-z]|inet '")
    
    def get_connections(self):
        """Get network connections"""
        return self._run_raw("netstat -an | grep ESTABLISHED | head -10")
    
    def ping(self, host="8.8.8.8", count=3):
        """Ping host"""
        return self.run_cmd(f"ping -c {count} {host}")
    
    def dns_lookup(self, hostname):
        """DNS lookup"""
        try:
            ip = socket.gethostbyname(hostname)
            return f"{hostname} -> {ip}"
        except:
            return f"Could not resolve {hostname}"
    
    # ===== DOCKER OPERATIONS =====
    def docker_ps(self):
        """List Docker containers"""
        return self._run_raw("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'")
    
    def docker_stats(self):
        """Docker stats"""
        return self._run_raw("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}'")
    
    def docker_images(self):
        """Docker images"""
        return self._run_raw("docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'")
    
    # ===== SERVICES =====
    def get_services(self):
        """Get launchctl services"""
        return self._run_raw("launchctl list | head -20")
    
    def service_action(self, action, service):
        """Start/stop service"""
        return self.run_cmd(f"launchctl {action} {service}")
    
    # ===== SYSTEM CONTROL =====
    def get_battery(self):
        """Battery status"""
        return self._run_raw("pmset -g batt")
    
    def volume_control(self, level=None):
        """Volume control"""
        if level is not None:
            return self.run_cmd(f"osascript -e 'set volume output volume {level}'")
        return self._run_raw("osascript -e 'get volume settings'")
    
    def brightness_control(self, level=None):
        """Brightness control (if available)"""
        return "Use keyboard brightness keys"
    
    def empty_trash(self):
        """Empty trash"""
        return self._run_raw("rm -rf ~/.Trash/* && echo 'Trash emptied'")
    
    # ===== QUICK ACTIONS =====
    def open_app(self, app_name):
        """Open application"""
        return self.run_cmd(f"open -a '{app_name}'")
    
    def system_report(self):
        """Get system report"""
        return self._run_raw("system_profiler | head -50")
    
    # ===== DASHBOARD =====
    def get_dashboard(self):
        """Get complete dashboard data"""
        return {
            'system': self.get_system_stats(),
            'top_procs': self.get_top_processes(5),
            'docker': self.docker_ps()[:200],
            'network': self.get_network_info()[:200],
            'battery': self.get_battery()[:100]
        }
    
    # ===== NATURAL LANGUAGE PROCESSING =====
    def process_command(self, user_input):
        """Process natural language commands"""
        cmd = user_input.lower()
        
        # Shell command passthrough for common utilities
        shell_utils = [
            'ls', 'pwd', 'date', 'whoami', 'uptime', 'uname', 
            'df', 'du', 'free', 'top', 'ps', 'env'
        ]
        
        # Exact utility match or starts with utility + space
        if any(cmd == util or cmd.startswith(util + ' ') for util in shell_utils):
            return self.run_cmd(cmd)

        # Default: use brain
        return None


def test():
    """Test orchestrator"""
    org = Orchestrator()
    print("=== SYSTEM STATS ===")
    print(org.get_system_stats())
    
    print("\n=== TOP PROCESSES ===")
    for p in org.get_top_processes(3):
        print(p)
    
    print("\n=== DOCKER ===")
    print(org.docker_ps())


if __name__ == "__main__":
    test()