#!/usr/bin/env python3
"""
JARVIS Brain Module — Advanced
Local LLM using Ollama with:
  - Conversation memory (sliding window)
  - System context awareness (time, machine state)
  - Intent detection (chat vs action requests)
  - Streaming for fast perceived response
  - No external dependencies (stdlib only)
"""

import json
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from collections import deque

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"

# Max conversation turns to keep in memory
MAX_HISTORY = 10


class JARVISBrain:
    def __init__(self, host=None, model=None):
        self.host = (host or os.environ.get("OLLAMA_HOST", OLLAMA_HOST)).rstrip("/")
        self.model = model or os.environ.get("JARVIS_CHAT_MODEL", DEFAULT_MODEL)
        self.system_prompt = self._load_system_prompt()
        self.history = deque(maxlen=MAX_HISTORY)
        self._system_context_cache = None
        self._system_context_ts = 0

    # ─── Prompt & Context ─────────────────────────────────────────

    def _load_system_prompt(self):
        """Load JARVIS personality prompt"""
        from jarvis.core.paths import system_prompt_path

        prompt_file = str(system_prompt_path())
        if os.path.exists(prompt_file):
            with open(prompt_file, 'r') as f:
                return f.read().strip()
        return (
            "You are J.A.R.V.I.S., Tony Stark's AI assistant. "
            "Be helpful, brief, slightly witty, and call the user 'sir'."
        )

    def _get_system_context(self, cwd=None):
        """Build live system context (cached for 30s)"""
        now = datetime.now()
        ts = now.timestamp()
        
        # Use provided CWD or fallback to current
        current_dir = cwd or os.getcwd()

        # Cache for 30 seconds to avoid slowdowns
        if self._system_context_cache and (ts - self._system_context_ts) < 30:
            # Only update time and CWD in the cached context
            cached = self._system_context_cache
            # Simple replacement for demonstration
            return f"Current time: {now.strftime('%I:%M %p, %A %d %B %Y')}\nCurrent directory: {current_dir}\n" + '\n'.join(cached.split('\n')[2:])

        parts = [
            f"Current time: {now.strftime('%I:%M %p, %A %d %B %Y')}",
            f"Current directory: {current_dir}"
        ]

        # Hostname
        try:
            import socket
            parts.append(f"Machine: {socket.gethostname()}")
        except Exception:
            pass

        # CPU
        try:
            result = subprocess.run(
                ['top', '-l', '1', '-n', '0'],
                capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.split('\n'):
                if 'CPU usage:' in line:
                    pct_parts = line.split('%')
                    user = float(pct_parts[0].split()[-1])
                    sys_usage = float(pct_parts[1].split()[0])
                    parts.append(f"CPU: {user + sys_usage:.0f}% used")
                    break
        except Exception:
            pass

        # Memory
        try:
            total_r = subprocess.run(
                ['sysctl', '-n', 'hw.memsize'],
                capture_output=True, text=True, timeout=2
            )
            total = int(total_r.stdout.strip())
            vm_r = subprocess.run(
                ['vm_stat'], capture_output=True, text=True, timeout=2
            )
            active = wired = 0
            for line in vm_r.stdout.split('\n'):
                if 'Pages active:' in line:
                    active = int(line.split()[-1].replace('.', '')) * 4096
                elif 'Pages wired down:' in line:
                    wired = int(line.split()[-1].replace('.', '')) * 4096
            used = active + wired
            parts.append(f"Memory: {used // 1024 // 1024}MB / {total // 1024 // 1024}MB ({used * 100 // total}%)")
        except Exception:
            pass

        # Battery
        try:
            batt_r = subprocess.run(
                ['pmset', '-g', 'batt'],
                capture_output=True, text=True, timeout=2
            )
            for line in batt_r.stdout.split('\n'):
                if '%' in line:
                    parts.append(f"Battery: {line.strip()}")
                    break
        except Exception:
            pass

        context = '\n'.join(parts)
        self._system_context_cache = context
        self._system_context_ts = ts
        return context

    def _build_prompt(self, user_input, extra_context=None, cwd=None, enable_tools=True):
        """Build a full prompt with system prompt, context, history, and user input"""
        sections = []

        if enable_tools:
            # System prompt enhancement for tool use (disabled for grounded-only prompts)
            tool_instr = (
                "\n## Tool Execution Protocol\n"
                "If you need to check the system, list files, or perform an action to answer the user, "
                "you MUST output a line starting with 'execute_command: ' followed by the shell command. "
                "Example: 'execute_command: ls -la'\n"
                "The HUD will execute it and give you the result. Use this for REAL information.\n"
            )
            sections.append(self.system_prompt + tool_instr)
        else:
            sections.append(self.system_prompt)

        # System context
        sys_ctx = self._get_system_context(cwd=cwd)
        sections.append(f"\n## Current System State\n{sys_ctx}")

        # Extra context (e.g., from RAG)
        if extra_context:
            sections.append(f"\n## Additional Context\n{extra_context}")

        # Conversation history
        if self.history:
            sections.append("\n## Recent Conversation")
            for role, msg in self.history:
                if role == 'user':
                    sections.append(f"User: {msg}")
                else:
                    # Truncate old assistant responses to save context
                    sections.append(f"JARVIS: {msg[:200]}")

        # Current message
        sections.append(f"\nUser: {user_input}\nJARVIS:")

        return '\n'.join(sections)

    # ─── Memory ───────────────────────────────────────────────────

    def remember(self, role, message):
        """Add a message to conversation history"""
        self.history.append((role, message))

    def clear_memory(self):
        """Clear conversation history"""
        self.history.clear()

    def get_memory_summary(self):
        """Get a summary of conversation history"""
        if not self.history:
            return "No conversation history."
        turns = len(self.history)
        return f"{turns} turns in memory (max {MAX_HISTORY})"

    # ─── Intent Detection ─────────────────────────────────────────

    def detect_intent(self, user_input):
        """Detect user intent from input.
        
        Returns one of:
            'command'   — user wants to run a system command
            'query'     — user is asking a factual question
            'chat'      — general conversation
            'action'    — user wants JARVIS to do something (open app, etc.)
        """
        lower = user_input.lower().strip()

        # Direct command patterns or simple CLI tools
        command_verbs = [
            'run ', 'execute ', 'show me ', 'list ', 'find ', 'check ',
            'what is my ', 'how much ', 'how many ',
        ]
        cli_tools = ['ls', 'pwd', 'date', 'top', 'ps', 'df', 'du', 'whoami', 'uname', 'cd']
        
        if any(lower.startswith(v) for v in command_verbs) or lower in cli_tools or any(lower.startswith(t + ' ') for t in cli_tools):
            return 'command'

        # Action patterns
        action_verbs = [
            'open ', 'launch ', 'start ', 'stop ', 'kill ', 'close ',
            'set volume', 'mute', 'play ', 'turn ',
        ]
        if any(lower.startswith(v) for v in action_verbs):
            return 'action'

        # Question patterns
        question_words = ['what', 'who', 'where', 'when', 'why', 'how', 'can you', 'do you']
        if any(lower.startswith(w) for w in question_words) or lower.endswith('?'):
            return 'query'

        return 'chat'

    # ─── Core Thinking ────────────────────────────────────────────

    def _send_request(self, request_data):
        """Send request to Ollama API"""
        data = json.dumps(request_data).encode('utf-8')
        req = urllib.request.Request(
            self.host + '/api/generate',
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        return urllib.request.urlopen(req, timeout=60)

    def think(
        self,
        user_input,
        context=None,
        cwd=None,
        enable_tools=True,
        memory_user_text=None,
    ):
        """Process input through LLM (non-streaming, returns full response)"""
        prompt = self._build_prompt(user_input, extra_context=context, cwd=cwd, enable_tools=enable_tools)

        request_data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 256,
            }
        }

        try:
            with self._send_request(request_data) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                response = result.get('response', 'I apologize, sir. Something went wrong.')

            # Remember the exchange
            self.remember('user', memory_user_text if memory_user_text is not None else user_input)
            self.remember('assistant', response)
            return response

        except urllib.error.URLError:
            return "Model unavailable, sir. Is Ollama running?"
        except TimeoutError:
            return "Request timed out, sir."
        except Exception as e:
            return f"Connection error: {str(e)}"

    def think_stream(
        self,
        user_input,
        context=None,
        callback=None,
        cwd=None,
        enable_tools=True,
        memory_user_text=None,
    ):
        """Process input through LLM with streaming.
        
        Args:
            user_input: The user's message
            context: Optional extra context to inject
            callback: Function called with each token as it arrives.
                      If None, tokens are printed to stdout.
            cwd: The current working directory to include in context
        
        Returns:
            The complete response string
        """
        prompt = self._build_prompt(user_input, extra_context=context, cwd=cwd, enable_tools=enable_tools)

        request_data = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 256,
            }
        }

        full_response = ""

        try:
            with self._send_request(request_data) as resp:
                buffer = ""
                while True:
                    chunk = resp.read(1)
                    if not chunk:
                        break

                    char = chunk.decode('utf-8', errors='replace')
                    buffer += char

                    # Each streamed JSON object ends with newline
                    if char == '\n' and buffer.strip():
                        try:
                            obj = json.loads(buffer.strip())
                            token = obj.get('response', '')
                            if token:
                                full_response += token
                                if callback:
                                    callback(token)
                                else:
                                    print(token, end="", flush=True)

                            if obj.get('done', False):
                                break
                        except json.JSONDecodeError:
                            pass
                        buffer = ""

            # Remember the exchange
            self.remember('user', memory_user_text if memory_user_text is not None else user_input)
            self.remember('assistant', full_response)

        except urllib.error.URLError:
            msg = "Model unavailable, sir. Is Ollama running?"
            if callback:
                callback(msg)
            else:
                print(msg)
            return msg
        except TimeoutError:
            msg = "Request timed out, sir."
            if callback:
                callback(msg)
            else:
                print(msg)
            return msg
        except Exception as e:
            msg = f"Connection error: {str(e)}"
            if callback:
                callback(msg)
            else:
                print(msg)
            return msg

        return full_response

    # ─── Utilities ────────────────────────────────────────────────

    def is_available(self):
        """Check if Ollama is reachable"""
        try:
            req = urllib.request.Request(self.host + '/')
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def summarize(self, text, max_words=50):
        """Summarize a block of text using the LLM"""
        prompt = (
            f"Summarize the following in under {max_words} words. "
            f"Be concise:\n\n{text[:2000]}"
        )
        return self.think(prompt)

    def chat(self):
        """Interactive chat mode with streaming and memory"""
        print("💬 JARVIS Chat Mode (streaming, with memory)")
        print("Type 'exit' to quit, 'clear' to reset memory\n")

        while True:
            user_input = input("You: ")
            lower = user_input.lower().strip()

            if lower in ['exit', 'quit']:
                print("Until next time, sir.")
                break

            if lower == 'clear':
                self.clear_memory()
                print("Memory cleared.\n")
                continue

            if lower == 'memory':
                print(f"Memory: {self.get_memory_summary()}\n")
                continue

            print("JARVIS: ", end="", flush=True)
            self.think_stream(user_input)
            print("\n")


if __name__ == "__main__":
    brain = JARVISBrain()
    brain.chat()