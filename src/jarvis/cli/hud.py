#!/usr/bin/env python3
"""
JARVIS Terminal HUD
Interactive AI-powered terminal assistant
"""

import os
import time
import subprocess
import threading
import shutil
import re
import unicodedata
from datetime import datetime

from jarvis.core.paths import get_jarvis_home

JARVIS_ROOT = str(get_jarvis_home())

try:
    from jarvis.core.shell_policy import REFUSAL_MESSAGE, shell_requires_consent
except Exception:  # pragma: no cover

    def shell_requires_consent(_cmd):
        return False

    REFUSAL_MESSAGE = "Command refused (policy module unavailable)."

# Colors for terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

# Colors
CYAN = "\033[36m"
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"

# Background
BG_BLUE = "\033[44m"
BG_CYAN = "\033[46m"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _load_brain():
    """Load brain module (lazy, may fail if Ollama is down)"""
    try:
        from jarvis.llm import JARVISBrain

        return JARVISBrain()
    except Exception:
        return None


def _load_orchestrator():
    """Load orchestrator"""
    try:
        from jarvis.runtime import Orchestrator

        return Orchestrator()
    except Exception:
        return None


def _load_skills():
    """Load skills"""
    try:
        from jarvis.runtime import SkillsManager

        return SkillsManager()
    except Exception:
        return None


def _load_agent(brain=None, orchestrator=None, skills=None):
    """Load general-purpose agent (grounded retrieval path)."""
    try:
        from jarvis.agent import GeneralPurposeAgent

        return GeneralPurposeAgent(brain=brain, orchestrator=orchestrator, skills=skills)
    except Exception:
        return None


def _load_smarthome():
    """Load smart home"""
    try:
        from jarvis.integrations import SmartHome

        return SmartHome()
    except Exception:
        return None


class HUD:
    def __init__(self):
        term_width = shutil.get_terminal_size((90, 24)).columns
        self.width = max(62, min(92, term_width - 4))
        self.running = False
        self.brain = None
        self.orchestrator = None
        self.skills = None
        self.smarthome = None
        self.agent = None
        self.pending_shell = None
        self.pending_note = None
        self.history = []
        self.cwd = os.getcwd()

    def init_modules(self):
        """Initialize all JARVIS modules"""
        print(f"\n{CYAN}{BOLD}  Initializing JARVIS modules...{RESET}")

        # Brain
        print(f"  {DIM}Loading brain (Ollama)...{RESET}", end="", flush=True)
        self.brain = _load_brain()
        if self.brain:
            print(f"\r  {GREEN}✓{RESET} Brain loaded ({self.brain.model})")
        else:
            print(f"\r  {YELLOW}⚠{RESET} Brain unavailable (is Ollama running?)")

        # Orchestrator
        print(f"  {DIM}Loading orchestrator...{RESET}", end="", flush=True)
        self.orchestrator = _load_orchestrator()
        if self.orchestrator:
            self.orchestrator.set_cwd(self.cwd)
            print(f"\r  {GREEN}✓{RESET} Orchestrator loaded            ")
        else:
            print(f"\r  {RED}✗{RESET} Orchestrator failed             ")

        # Skills
        print(f"  {DIM}Loading skills...{RESET}", end="", flush=True)
        self.skills = _load_skills()
        if self.skills:
            count = len(self.skills.list_skills())
            print(f"\r  {GREEN}✓{RESET} Skills loaded ({count} skills)   ")
        else:
            print(f"\r  {RED}✗{RESET} Skills failed                    ")

        # Agent (grounded work partner)
        print(f"  {DIM}Loading work partner agent...{RESET}", end="", flush=True)
        self.agent = _load_agent(brain=self.brain, orchestrator=self.orchestrator, skills=self.skills)
        if self.agent:
            if self.agent.work_partner.is_available():
                try:
                    self.agent.work_partner.bootstrap_schema()
                    print(f"\r  {GREEN}✓{RESET} Work partner online (Neo4j)      ")
                except Exception:
                    print(f"\r  {YELLOW}⚠{RESET} Work partner degraded (Neo4j) ")
            else:
                print(f"\r  {YELLOW}⚠{RESET} Work partner offline (Neo4j)    ")
        else:
            print(f"\r  {RED}✗{RESET} Work partner failed             ")

        # Smart Home
        print(f"  {DIM}Loading smart home...{RESET}", end="", flush=True)
        self.smarthome = _load_smarthome()
        if self.smarthome:
            print(f"\r  {GREEN}✓{RESET} Smart home loaded              ")
        else:
            print(f"\r  {YELLOW}⚠{RESET} Smart home unavailable         ")

        print()

    def clear_screen(self):
        os.system('clear')

    def header(self):
        """JARVIS header"""
        line = "═" * self.width
        title = "JARVIS // TACTICAL TERMINAL HUD"
        subtitle = f"{DIM}JUST A RATHER VERY INTELLIGENT SYSTEM{RESET}"
        title_padding = max(0, self.width - 1 - self._visible_len(title))
        subtitle_padding = max(0, self.width - 1 - self._visible_len(subtitle))
        return f"""
{CYAN}{BOLD}╔{line}╗
║ {title}{' ' * title_padding}║
║ {subtitle}{' ' * subtitle_padding}║
╚{line}╝{RESET}
"""

    def _visible_len(self, text):
        """Measure display width without ANSI color codes."""
        clean = ANSI_RE.sub("", text)
        width = 0
        for ch in clean:
            if unicodedata.combining(ch):
                continue
            width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        return width

    def status_box(self, title, content, color=CYAN):
        """Status box with proper alignment"""
        lines = content.split('\n')
        title_pad = max(0, self.width - self._visible_len(title) - 5)
        box = f"{color}╭─ {title} {'─' * title_pad}╮{RESET}\n"
        for line in lines[:8]:
            padding = self.width - 4 - self._visible_len(line)
            if padding < 0:
                padding = 0
            box += f"{color}│{RESET} {line}{' ' * padding} {color}│{RESET}\n"
        box += f"{color}╰{'─' * (self.width - 2)}╯{RESET}"
        return box

    def get_module_status(self):
        """Get module load/health summary"""
        brain_state = f"{GREEN}ONLINE{RESET}" if self.brain else f"{YELLOW}DEGRADED{RESET}"
        orchestrator_state = f"{GREEN}ONLINE{RESET}" if self.orchestrator else f"{RED}OFFLINE{RESET}"
        skills_state = f"{GREEN}ONLINE{RESET}" if self.skills else f"{RED}OFFLINE{RESET}"
        home_state = f"{GREEN}ONLINE{RESET}" if self.smarthome else f"{YELLOW}DEGRADED{RESET}"
        kg_state = f"{YELLOW}OFFLINE{RESET}"
        if self.agent and self.agent.work_partner.is_available():
            kg_state = f"{GREEN}ONLINE{RESET}"
        elif self.agent:
            kg_state = f"{YELLOW}DEGRADED{RESET}"

        skills_count = len(self.skills.list_skills()) if self.skills else 0
        return f"""{GREEN}●{RESET} Brain:        {brain_state}
{GREEN}●{RESET} Orchestrator: {orchestrator_state}
{GREEN}●{RESET} Skills:       {skills_state}  ({skills_count} loaded)
{GREEN}●{RESET} Smart Home:   {home_state}
{GREEN}●{RESET} Knowledge:    {kg_state}"""

    def get_session_status(self):
        """Get current session summary"""
        cwd_display = self.cwd.replace(os.path.expanduser('~'), '~')
        if len(cwd_display) > 42:
            cwd_display = "..." + cwd_display[-39:]

        last_cmd = self.history[-1] if self.history else "None yet"
        if len(last_cmd) > 42:
            last_cmd = last_cmd[:39] + "..."

        return f"""{CYAN}•{RESET} Commands run: {WHITE}{len(self.history)}{RESET}
{CYAN}•{RESET} Last command: {DIM}{last_cmd}{RESET}
{CYAN}•{RESET} Working dir:  {DIM}{cwd_display}{RESET}
{CYAN}•{RESET} Help:         {WHITE}type 'help' for full command map{RESET}"""

    def get_system_status(self):
        """Get live system info"""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%d %b %Y, %A")

        # CPU
        cpu_str = "..."
        try:
            result = subprocess.run(
                ['top', '-l', '1', '-n', '0'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'CPU usage:' in line:
                    parts = line.split('%')
                    user = float(parts[0].split()[-1])
                    sys_usage = float(parts[1].split()[0])
                    cpu_val = user + sys_usage
                    if cpu_val < 50:
                        cpu_color = GREEN
                    elif cpu_val < 80:
                        cpu_color = YELLOW
                    else:
                        cpu_color = RED
                    cpu_str = f"{cpu_color}{cpu_val:.1f}%{RESET}"
                    break
        except Exception:
            cpu_str = f"{DIM}N/A{RESET}"

        # Memory
        mem_str = "..."
        try:
            total_result = subprocess.run(
                ['sysctl', '-n', 'hw.memsize'],
                capture_output=True, text=True, timeout=3
            )
            total = int(total_result.stdout.strip())

            vm_result = subprocess.run(
                ['vm_stat'], capture_output=True, text=True, timeout=3
            )
            active = wired = 0
            for line in vm_result.stdout.split('\n'):
                if 'Pages active:' in line:
                    active = int(line.split()[-1].replace('.', '')) * 4096
                elif 'Pages wired down:' in line:
                    wired = int(line.split()[-1].replace('.', '')) * 4096

            used = active + wired
            pct = used / total * 100
            if pct < 60:
                mem_color = GREEN
            elif pct < 85:
                mem_color = YELLOW
            else:
                mem_color = RED
            mem_str = f"{mem_color}{pct:.0f}%{RESET} ({used // 1024 // 1024}MB / {total // 1024 // 1024}MB)"
        except Exception:
            mem_str = f"{DIM}N/A{RESET}"

        # Disk
        disk_str = "..."
        try:
            result = subprocess.run(
                ['df', '-h', '/'], capture_output=True, text=True, timeout=3
            )
            parts = result.stdout.strip().split('\n')[1].split()
            disk_pct = int(parts[4].replace('%', ''))
            if disk_pct < 70:
                disk_color = GREEN
            elif disk_pct < 90:
                disk_color = YELLOW
            else:
                disk_color = RED
            disk_str = f"{disk_color}{parts[4]}{RESET} ({parts[2]} / {parts[1]})"
        except Exception:
            disk_str = f"{DIM}N/A{RESET}"

        # Ollama status
        ollama_str = f"{RED}Offline{RESET}"
        try:
            result = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                 'http://localhost:11434/'],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip() == '200':
                ollama_str = f"{GREEN}Online{RESET}"
            else:
                ollama_str = f"{YELLOW}Starting{RESET}"
        except Exception:
            pass

        # Current directory
        cwd_display = self.cwd.replace(os.path.expanduser('~'), '~')
        if len(cwd_display) > 40:
            cwd_display = '...' + cwd_display[-37:]

        return f"""{GREEN}✓{RESET} Time:    {WHITE}{time_str}{RESET}  •  {date_str}
{GREEN}✓{RESET} CPU:     {cpu_str}
{GREEN}✓{RESET} Memory:  {mem_str}
{GREEN}✓{RESET} Disk:    {disk_str}
{GREEN}✓{RESET} Ollama:  {ollama_str}
{CYAN}>{RESET} CWD:     {DIM}{cwd_display}{RESET}"""

    def get_quick_actions(self):
        """Quick action menu"""
        return f"""{YELLOW}Core:{RESET} {CYAN}status{RESET}, {CYAN}ps{RESET}, {CYAN}skills{RESET}, {CYAN}history{RESET}
{YELLOW}Partner:{RESET} {CYAN}ask <q>{RESET}, {CYAN}ingest <path>{RESET}, {CYAN}kg status{RESET}
{YELLOW}Execution:{RESET} {CYAN}shell <cmd>{RESET}, {CYAN}$ <cmd>{RESET}, {CYAN}! <cmd>{RESET}
{YELLOW}System:{RESET} {CYAN}battery{RESET}, {CYAN}wifi{RESET}, {CYAN}docker{RESET}, {CYAN}ip{RESET}
{YELLOW}Control:{RESET} {CYAN}clear{RESET}, {CYAN}help{RESET}, {CYAN}exit{RESET}
{DIM}Tip: ask naturally, JARVIS will route to orchestrator/skills/brain automatically.{RESET}"""

    def render(self):
        """Render full HUD"""
        self.clear_screen()

        print(self.header())

        # Live system status
        print(self.status_box("SYSTEM STATUS", self.get_system_status()))
        print()

        # Module health
        print(self.status_box("MODULE HEALTH", self.get_module_status(), color=GREEN))
        print()

        # Commands
        print(self.status_box("COMMANDS", self.get_quick_actions()))
        print()

        # Session
        print(self.status_box("SESSION", self.get_session_status(), color=MAGENTA))
        print()

        # Footer
        print(f"{DIM}{'─' * self.width}{RESET}")
        print(f"{CYAN}Type a command, ask a question, or use 'clear' to redraw • 'exit' to quit{RESET}")

    def print_response(self, text, prefix="JARVIS"):
        """Print a formatted response"""
        print(f"\n  {CYAN}{BOLD}{prefix}:{RESET} ", end="")

        # Print line by line with indentation
        lines = str(text).split('\n')
        for i, line in enumerate(lines):
            if i == 0:
                print(line)
            else:
                print(f"          {line}")
        print()

    def print_error(self, text):
        """Print error message"""
        print(f"\n  {RED}✗ {text}{RESET}\n")

    def print_info(self, text):
        """Print info"""
        print(f"\n  {DIM}{text}{RESET}\n")

    def _print_grounded_payload(self, payload):
        """Render grounded agent output with citations and safe actions."""
        answer = payload.get("answer", "")
        confidence = payload.get("confidence", 0.0)
        conflicts = payload.get("conflicts") or []
        citations = payload.get("citations") or []
        actions = payload.get("suggested_actions") or []
        timings = payload.get("timings_ms") or {}

        print(f"\n  {CYAN}{BOLD}JARVIS:{RESET} ", end="")
        print(answer)

        print(f"\n  {DIM}Confidence:{RESET} {confidence:.2f}")
        if timings:
            parts = []
            for k, v in timings.items():
                if k == "vector_note":
                    parts.append(f"{k}={v}")
                else:
                    parts.append(f"{k}={v}ms")
            print(f"  {DIM}Retrieval:{RESET} {', '.join(parts)}")

        if conflicts:
            print(f"\n  {YELLOW}Conflicts:{RESET}")
            for item in conflicts:
                print(f"    - {item}")

        if citations:
            print(f"\n  {CYAN}Sources:{RESET}")
            for cite in citations[:12]:
                cid = cite.get("id", "?")
                src = cite.get("source", "?")
                idx = cite.get("chunk", "?")
                score = cite.get("score", 0.0)
                print(f"    {DIM}{cid}{RESET} {src}#{idx} ({score:.2f})")

        if actions:
            print(f"\n  {MAGENTA}Suggested actions (confirm with 'yes'):{RESET}")
            primary = None
            for i, act in enumerate(actions, 1):
                title = getattr(act, "title", "Action")
                cmd = getattr(act, "command", "")
                risk = getattr(act, "risk_level", "unknown")
                why = getattr(act, "why", "")
                print(f"    {i}. {title} [{risk}]")
                print(f"       {DIM}{why}{RESET}")
                print(f"       {CYAN}$ {cmd}{RESET}")
                if primary is None:
                    primary = cmd
            if primary:
                self.pending_shell = primary
                self.pending_note = "pending_confirmation"

        print()

    def _handle_ask(self, question, stream=False):
        if not self.agent:
            self.print_error("Work partner agent not available")
            return
        payload = self.agent.process_grounded(question, cwd=self.cwd, stream=stream)
        self._print_grounded_payload(payload)

    def _handle_kg_command(self, cmd_lower, raw_cmd):
        if not self.agent or not self.agent.work_partner:
            self.print_error("Knowledge graph unavailable")
            return

        parts = raw_cmd.strip().split()
        sub = parts[1].lower() if len(parts) > 1 else "status"

        if sub in ("status", "info"):
            self.print_response(self.agent.work_partner.status(), prefix="KG")
            return

        if sub == "bootstrap":
            try:
                self.agent.work_partner.bootstrap_schema()
                self.print_info("Neo4j schema bootstrapped.")
            except Exception as exc:
                self.print_error(f"Bootstrap failed: {exc}")
            return

        self.print_error("Usage: kg status | kg bootstrap")

    def _handle_ingest(self, raw_cmd):
        path = raw_cmd.split(" ", 1)[1].strip() if " " in raw_cmd else ""
        if not path:
            self.print_error("Usage: ingest <file_path>")
            return
        expanded = os.path.expanduser(path)
        if not os.path.isfile(expanded):
            self.print_error(f"File not found: {expanded}")
            return

        try:
            from jarvis.rag import KnowledgeBase
            kb = KnowledgeBase(work_partner=self.agent.work_partner if self.agent else None)
            filename = os.path.basename(expanded)
            with open(expanded, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
            msg = kb.add_document(filename, content=content)
            self.print_response(msg, prefix="INGEST")
        except Exception as exc:
            self.print_error(f"Ingest failed: {exc}")

    def _extract_check_request(self, cmd):
        """Split '<command> | check ...' into command and analysis prompt."""
        lower = cmd.lower().strip()

        # Fast path for common natural-language pipe intents.
        if "|" in cmd:
            shell_part, ask_part = cmd.split("|", 1)
            shell_part = shell_part.strip()
            ask_part = ask_part.strip()
            analysis_verbs = {
                "check", "explain", "summarize", "summary", "set",
                "analyze", "review", "inspect", "tell"
            }
            first_word = ask_part.split()[0].lower() if ask_part else ""
            if shell_part and first_word in analysis_verbs:
                return shell_part, ask_part

        markers = [
            " | check ", "|check ",
            " | explain ", "|explain ",
            " | summarize ", "|summarize ",
            " | set ", "|set ",
            " | analyze ", "|analyze ",
            " | review ", "|review ",
        ]
        for marker in markers:
            idx = lower.find(marker)
            if idx != -1:
                shell_part = cmd[:idx].strip()
                ask_part = cmd[idx + len(marker):].strip()
                if shell_part:
                    analysis = ask_part or "analyze this output briefly"
                    return shell_part, analysis
        return cmd.strip(), None

    def _run_shell_capture(self, cmd, force_allow=False):
        """Run shell command and return (ok, output)."""
        cmd_strip = cmd.strip()

        success, msg = self._handle_cd(cmd_strip)
        if success:
            return True, msg
        if msg:
            return False, msg

        if not force_allow and shell_requires_consent(cmd_strip):
            self.pending_shell = cmd_strip
            self.pending_note = "pending_confirmation"
            return False, (
                f"{REFUSAL_MESSAGE}\n"
                "Type `yes` to run this exact command once, or `cancel` to dismiss."
            )

        try:
            result = subprocess.run(
                cmd, shell=True, cwd=self.cwd,
                capture_output=True, text=True, timeout=30
            )
            output = (result.stdout or "") + (result.stderr or "")
            if not output.strip():
                output = "(no output)"
            return result.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out (30s limit)"
        except Exception as e:
            return False, f"Error: {e}"

    def _brain_check_output(self, command, output, request):
        """Ask brain to analyze command output when requested."""
        if not self.brain:
            return
        prompt = (
            "You are JARVIS. Analyze this command result briefly and clearly.\n"
            f"Command: {command}\n"
            f"User request: {request}\n\n"
            f"Output:\n{output}\n\n"
            "Return key findings and next action in <= 6 lines."
        )
        print(f"\n  {CYAN}{BOLD}JARVIS (Analysis):{RESET} ", end="", flush=True)
        try:
            self.brain.think_stream(prompt, cwd=self.cwd)
            print("\n")
        except Exception as e:
            print()
            self.print_error(f"Brain analysis failed: {e}")

    def handle_command(self, cmd):
        """Route command to the right module"""
        cmd_lower = cmd.lower().strip()
        self.history.append(cmd)

        # === Built-in HUD commands ===
        if cmd_lower in ['exit', 'quit', 'q']:
            print(f"\n{MAGENTA}  Goodbye, sir. Systems standing by.{RESET}\n")
            self.running = False
            return

        if cmd_lower == 'clear':
            self.render()
            return

        if cmd_lower in ['status', 'stats', 'sys']:
            print(f"\n{self.status_box('SYSTEM STATUS', self.get_system_status())}\n")
            return

        if cmd_lower in ['help', 'h', '?']:
            self._show_help()
            return

        if cmd_lower == 'history':
            self._show_history()
            return

        if cmd_lower in ('no', 'n', 'cancel', 'abort'):
            if self.pending_shell and self.pending_note == "pending_confirmation":
                self.pending_shell = None
                self.pending_note = None
                self.print_info("Pending command cancelled, sir.")
            else:
                self.print_info("No pending command to cancel.")
            return

        if cmd_lower in ('yes', 'y', 'confirm', 'run'):
            if self.pending_shell and self.pending_note == "pending_confirmation":
                shell_cmd = self.pending_shell
                self.pending_shell = None
                self.pending_note = None
                print(f"\n  {DIM}$ {shell_cmd}{RESET}")
                ok, output = self._run_shell_capture(shell_cmd, force_allow=True)
                for line in output.split('\n'):
                    print(f"  {line}")
                if not ok:
                    self.print_error("Suggested command returned non-zero exit status.")
                if self.brain:
                    verify_prompt = (
                        "You are JARVIS. Summarize the command output below and state whether the intent succeeded.\n"
                        f"Command: {shell_cmd}\n\nOutput:\n{output}\n"
                    )
                    print(f"\n  {CYAN}{BOLD}JARVIS (Verify):{RESET} ", end="", flush=True)
                    self.brain.think_stream(verify_prompt, cwd=self.cwd)
                    print("\n")
                print()
            else:
                self.print_info("No pending action to confirm.")
            return

        if cmd_lower.startswith('ask ') or cmd_lower.startswith('partner '):
            question = cmd.split(' ', 1)[1].strip()
            self._handle_ask(question, stream=False)
            return

        if cmd_lower.startswith('kg'):
            self._handle_kg_command(cmd_lower, cmd)
            return

        if cmd_lower.startswith('ingest '):
            self._handle_ingest(cmd)
            return

        # === Processes ===
        if cmd_lower in ['ps', 'top', 'processes']:
            self._show_processes()
            return

        if cmd_lower.startswith('kill '):
            pid = cmd_lower.split()[1]
            self._kill_process(pid)
            return

        # === Skills ===
        if cmd_lower in ['skills', 'skill']:
            self._show_skills()
            return

        # === Memory commands ===
        if cmd_lower in ['memory', 'mem']:
            if self.brain:
                self.print_info(f"Brain memory: {self.brain.get_memory_summary()}")
            else:
                self.print_error("Brain not loaded")
            return

        if cmd_lower in ['forget', 'clear memory', 'reset']:
            if self.brain:
                self.brain.clear_memory()
                self.print_info("Conversation memory cleared.")
            return

        # === Shell command ===
        if cmd_lower.startswith('shell ') or cmd_lower.startswith('$ ') or cmd_lower.startswith('! '):
            raw_shell_cmd = cmd[cmd.index(' ') + 1:]
            shell_cmd, check_request = self._extract_check_request(raw_shell_cmd)
            if check_request:
                print(f"\n  {DIM}$ {shell_cmd}{RESET}")
                ok, output = self._run_shell_capture(shell_cmd)
                for line in output.split('\n'):
                    print(f"  {line}")
                if (
                    not ok
                    and self.pending_note == "pending_confirmation"
                    and self.pending_shell
                    and self.pending_shell.strip() == shell_cmd.strip()
                ):
                    print()
                    return
                if not ok:
                    self.print_error("Command returned a non-zero exit status.")
                self._brain_check_output(shell_cmd, output, check_request)
                print()
            else:
                self._run_shell(shell_cmd)
            return

        # === Smart Home shortcuts ===
        if cmd_lower.startswith('volume '):
            try:
                level = int(cmd_lower.split()[1])
                if self.smarthome:
                    result = self.smarthome.volume(level)
                    self.print_response(result)
                else:
                    self.print_error("Smart home module not loaded")
            except ValueError:
                self.print_error("Usage: volume <0-100>")
            return

        if cmd_lower in ['battery', 'batt']:
            self._run_shell("pmset -g batt")
            return

        if cmd_lower in ['wifi', 'network', 'net']:
            if self.smarthome:
                result = self.smarthome.wifi_status()
                self.print_response(result)
            else:
                self._run_shell("networksetup -getairportnetwork en0")
            return

        if cmd_lower == 'docker' or cmd_lower == 'containers':
            self._run_shell("docker ps -a 2>/dev/null || echo 'Docker not running'")
            return

        if cmd_lower.startswith('docker '):
            # Allow: docker ... | check ...
            docker_cmd, check_request = self._extract_check_request(cmd)
            if check_request:
                print(f"\n  {DIM}$ {docker_cmd}{RESET}")
                ok, output = self._run_shell_capture(docker_cmd)
                for line in output.split('\n'):
                    print(f"  {line}")
                if (
                    not ok
                    and self.pending_note == "pending_confirmation"
                    and self.pending_shell
                    and self.pending_shell.strip() == docker_cmd.strip()
                ):
                    print()
                    return
                if not ok and "docker" in output.lower():
                    self.print_error("Docker command failed.")
                self._brain_check_output(docker_cmd, output, check_request)
                print()
            else:
                self._run_shell(f"{cmd} 2>/dev/null || echo 'Docker command failed'")
            return

        if cmd_lower in ['ip', 'myip']:
            self._run_shell("curl -s ifconfig.me && echo")
            return

        # === Try matching a skill ===
        if self.skills:
            skill_name = self.skills.match_skill(cmd_lower)
            if skill_name:
                parts = cmd.split(' ', 1)
                if len(parts) > 1:
                    result = self.skills.execute(skill_name, parts[1])
                else:
                    result = self.skills.execute(skill_name)
                self.print_response(result)
                return

        # === Use brain intent detection to route smarter ===
        intent = None
        if self.brain:
            intent = self.brain.detect_intent(cmd)

        # Try orchestrator for command/action intents first
        if self.orchestrator and intent in ('command', 'action'):
            self.orchestrator.set_cwd(self.cwd)
            result = self.orchestrator.process_command(cmd)
            if result is not None:
                if isinstance(result, dict):
                    for k, v in result.items():
                        print(f"  {CYAN}{k}:{RESET} {v}")
                    print()
                elif isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            name = item.get('name', '?')[:30]
                            cpu = item.get('cpu', '?')
                            mem = item.get('mem', '?')
                            pid = item.get('pid', '?')
                            print(f"  {DIM}{pid}{RESET}  {YELLOW}{cpu}%{RESET}  {GREEN}{mem}%{RESET}  {name}")
                        else:
                            print(f"  {item}")
                    print()
                else:
                    self.print_response(result)
                return

        # Also try orchestrator for any unmatched input (no intent needed)
        if self.orchestrator and intent not in ('command', 'action'):
            self.orchestrator.set_cwd(self.cwd)
            result = self.orchestrator.process_command(cmd)
            if result is not None:
                if isinstance(result, dict):
                    for k, v in result.items():
                        print(f"  {CYAN}{k}:{RESET} {v}")
                    print()
                elif isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            name = item.get('name', '?')[:30]
                            cpu = item.get('cpu', '?')
                            mem = item.get('mem', '?')
                            pid = item.get('pid', '?')
                            print(f"  {DIM}{pid}{RESET}  {YELLOW}{cpu}%{RESET}  {GREEN}{mem}%{RESET}  {name}")
                        else:
                            print(f"  {item}")
                    print()
                else:
                    self.print_response(result)
                return

        # === Fall back to grounded agent or brain chat ===
        if self.agent:
            try:
                payload = self.agent.process_grounded(cmd, cwd=self.cwd, stream=False)
                self._print_grounded_payload(payload)
            except Exception as e:
                self.print_error(f"Agent error: {e}")
        elif self.brain:
            print(f"\n  {CYAN}{BOLD}JARVIS:{RESET} ", end="", flush=True)
            try:
                response = self.brain.think_stream(cmd, cwd=self.cwd)
                print("\n")

                if 'execute_command:' in response:
                    for line in response.split('\n'):
                        if 'execute_command:' in line:
                            tool_cmd = line.split('execute_command:')[1].strip()
                            self.print_info(f"AI requested execution: {tool_cmd}")

                            if tool_cmd.startswith('cd '):
                                success, msg = self._handle_cd(tool_cmd)
                                output = msg if success else f"Error: {msg}"
                            elif self.orchestrator:
                                self.orchestrator.set_cwd(self.cwd)
                                output = self.orchestrator.run_cmd(tool_cmd)
                            else:
                                output = "Orchestrator not available."

                            print(f"  {CYAN}{BOLD}JARVIS (Result):{RESET} ", end="", flush=True)
                            self.brain.think_stream(
                                f"The command '{tool_cmd}' returned this output:\n\n{output}\n\nPlease summarize this for me, sir.",
                                cwd=self.cwd
                            )
                            print("\n")
            except Exception as e:
                print()
                self.print_error(f"Brain error: {e}")
        else:
            self.print_error(
                "Brain not available. Start Ollama with: ollama serve"
            )
            self.print_info("You can still use built-in commands. Type 'help' for a list.")

    def _show_help(self):
        """Show full help"""
        help_text = f"""
  {CYAN}{BOLD}JARVIS HUD - Command Reference{RESET}

  {YELLOW}System:{RESET}
    status, stats     Refresh system statistics
    ps, top           Top processes by CPU
    kill <pid>        Kill a process
    battery           Battery status
    wifi, network     Network info
    docker            Docker containers
    ip, myip          Public IP address

  {YELLOW}Shell:{RESET}
    shell <cmd>       Run any shell command
    $ <cmd>           Shortcut for shell
    ! <cmd>           Shortcut for shell

  {YELLOW}Skills:{RESET}
    skills            List available skills
    weather <city>    Get weather
    time              Current time
    search <query>    Web search
    open <app>        Open application
    system <cmd>      Run system command

  {YELLOW}Smart Home:{RESET}
    volume <0-100>    Set volume

  {YELLOW}AI Chat:{RESET}
    Just type naturally! JARVIS will respond via Ollama.
    ask <question>    Grounded answer with citations (Neo4j + embeddings)
    ingest <path>     Ingest a text file into the knowledge graph
    kg status         Knowledge graph connectivity
    kg bootstrap      Create Neo4j constraints/indexes
    yes               Confirm the pending shell command (suggested or privileged)
    cancel            Clear a pending privileged command without running it
    memory            Show conversation memory status
    forget, reset     Clear conversation memory

  {YELLOW}HUD:{RESET}
    clear             Redraw HUD
    history           Command history
    help              This help
    exit, quit        Exit JARVIS
"""
        print(help_text)

    def _show_processes(self):
        """Show top processes"""
        if self.orchestrator:
            procs = self.orchestrator.get_top_processes(10)
            print(f"\n  {CYAN}{BOLD}TOP PROCESSES{RESET}")
            print(f"  {DIM}{'PID':<8} {'CPU%':<7} {'MEM%':<7} {'NAME'}{RESET}")
            print(f"  {DIM}{'─'*50}{RESET}")
            for p in procs:
                cpu = float(p.get('cpu', 0))
                if cpu > 50:
                    cpu_color = RED
                elif cpu > 20:
                    cpu_color = YELLOW
                else:
                    cpu_color = GREEN
                print(f"  {DIM}{p['pid']:<8}{RESET} {cpu_color}{p['cpu']:<7}{RESET} {p['mem']:<7} {p['name']}")
            print()
        else:
            self._run_shell("ps aux -r | head -11")

    def _kill_process(self, pid):
        """Kill a process"""
        if self.orchestrator:
            result = self.orchestrator.kill_process(pid)
            if "Error" in str(result):
                self.print_error(f"Failed to kill PID {pid}: {result}")
            else:
                self.print_response(f"Process {pid} terminated.")
        else:
            self._run_shell(f"kill {pid}")

    def _show_skills(self):
        """Show available skills"""
        if self.skills:
            skills_list = self.skills.list_skills()
            print(f"\n  {CYAN}{BOLD}AVAILABLE SKILLS{RESET}")
            print(f"  {DIM}{'─'*40}{RESET}")
            for name, desc in skills_list.items():
                print(f"  {CYAN}{name:<14}{RESET} {desc}")
            print()
        else:
            self.print_error("Skills module not loaded")

    def _handle_cd(self, cmd_strip):
        """Helper to handle directory changes and sync state"""
        if cmd_strip.startswith('cd '):
            new_path = cmd_strip[3:].strip().strip('"').strip("'")
            try:
                # Proper path resolution: handle ~, absolute, and relative paths
                if new_path.startswith('~'):
                    target = os.path.abspath(os.path.expanduser(new_path))
                elif new_path.startswith('/'):
                    target = os.path.abspath(new_path)
                else:
                    target = os.path.abspath(os.path.join(self.cwd, new_path))
                
                if os.path.isdir(target):
                    self.cwd = target
                    if self.orchestrator:
                        self.orchestrator.set_cwd(self.cwd)
                    return True, f"Changed directory to {self.cwd}"
                else:
                    return False, f"Directory not found: {new_path}"
            except Exception as e:
                return False, f"cd failed: {e}"
        return False, None

    def _run_shell(self, cmd, force_allow=False):
        """Run shell command and display output"""
        cmd_strip = cmd.strip()
        
        # Intercept 'cd'
        success, msg = self._handle_cd(cmd_strip)
        if success:
            return
        elif msg: # Error during cd
            self.print_error(msg)
            return

        if not force_allow and shell_requires_consent(cmd_strip):
            self.pending_shell = cmd_strip
            self.pending_note = "pending_confirmation"
            print(f"\n  {YELLOW}Approval required (privileged or destructive command).{RESET}")
            print(f"  {DIM}$ {cmd_strip}{RESET}")
            print(f"  {DIM}{REFUSAL_MESSAGE}{RESET}")
            print(f"  {CYAN}Type `yes` once to execute, or `cancel` to dismiss.{RESET}\n")
            return

        print(f"\n  {DIM}$ {cmd}{RESET}")
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=self.cwd,
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            if output.strip():
                for line in output.strip().split('\n'):
                    print(f"  {line}")
            else:
                print(f"  {DIM}(no output){RESET}")
        except subprocess.TimeoutExpired:
            self.print_error("Command timed out (30s limit)")
        except Exception as e:
            self.print_error(f"Error: {e}")
        print()

    def _show_history(self):
        """Show command history"""
        if not self.history:
            self.print_info("No commands in history yet.")
            return
        print(f"\n  {CYAN}{BOLD}COMMAND HISTORY{RESET}")
        for i, cmd in enumerate(self.history[-20:], 1):
            print(f"  {DIM}{i:>3}.{RESET} {cmd}")
        print()

    def run(self):
        """Run HUD loop"""
        self.running = True

        self.clear_screen()
        print(self.header())
        self.init_modules()
        self.render()

        while self.running:
            try:
                cmd = input(f"\n{BOLD}JARVIS>{RESET} ").strip()

                if not cmd:
                    continue

                self.handle_command(cmd)

            except (KeyboardInterrupt, EOFError):
                print(f"\n\n{MAGENTA}  Goodbye, sir. Systems standing by.{RESET}\n")
                self.running = False


def run_hud():
    """Run HUD"""
    hud = HUD()
    hud.run()


def main():
    """Console entry: jarvis-hud"""
    run_hud()


if __name__ == "__main__":
    main()