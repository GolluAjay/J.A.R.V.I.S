#!/usr/bin/env python3
"""
JARVIS Skills System
Extend JARVIS with custom commands
"""

import os
import subprocess
import json

from jarvis.core.shell_policy import REFUSAL_MESSAGE, shell_requires_consent

class Skill:
    def __init__(self, name, description, function):
        self.name = name
        self.description = description
        self.function = function
    
    def execute(self, *args):
        try:
            return self.function(*args)
        except TypeError:
            # If function doesn't take args, call without
            return self.function()


class SkillsManager:
    def __init__(self, skills_dir=None):
        if skills_dir:
            self.skills_dir = skills_dir
        else:
            from jarvis.core.paths import skills_dir as _skills_dir

            self.skills_dir = str(_skills_dir())
        
        self.skills = {}
        self.load_builtin_skills()
    
    def load_builtin_skills(self):
        """Load built-in skills"""
        
        # System skill - execute shell commands
        def system_command(command=None):
            if not command:
                return "Usage: system <command>"
            if shell_requires_consent(command):
                return REFUSAL_MESSAGE + " Use `shell <command>` in the HUD and type `yes` once."
            result = subprocess.run(
                command, shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout[:500] if result.returncode == 0 else result.stderr[:500]
        
        self.register("system", "Execute shell commands", system_command)
        
        # Open app skill  
        def open_app(app_name=None):
            if not app_name:
                return "Usage: open <app_name> (e.g., Safari, Terminal)"
            result = subprocess.run(
                ['open', '-a', app_name],
                capture_output=True,
                text=True
            )
            return f"Opening {app_name}" if result.returncode == 0 else f"Error: {result.stderr}"
        
        self.register("open", "Open applications", open_app)
        self.register("weather", "Get weather info", self._weather)
        self.register("time", "Get current time", self._time)
        self.register("search", "Search the web", self._search)
        self.register("knowledge", "Search knowledge base", self._knowledge)
    
    def _weather(self, location="London"):
        """Get weather"""
        result = subprocess.run(
            f'curl -s "wttr.in/{location}?format=%c+%t"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return f"Weather: {result.stdout}" if result.stdout else "Weather unavailable"
    
    def _time(self):
        """Get current time"""
        result = subprocess.run(['date'], capture_output=True, text=True)
        return result.stdout.strip()
    
    def _search(self, query=None):
        """Search the web using DuckDuckGo"""
        if not query:
            return "Usage: search <query>"
        # Use curl to DuckDuckGo API
        result = subprocess.run(
            f'curl -s "https://api.duckduckgo.com/?q={query}&format=json"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        try:
            import json
            data = json.loads(result.stdout)
            return data.get('AbstractText', f'No results for: {query}')[:300]
        except:
            return result.stdout[:300] if result.stdout else f"Search for: {query}"
    
    def _knowledge(self, query=None):
        """Search knowledge base"""
        try:
            from jarvis.rag import KnowledgeBase
            kb = KnowledgeBase()
            if not query:
                return f"Knowledge base: {kb.status()}\nDocs: {kb.list_documents()}"
            result = kb.query(query)
            return result if result else "No relevant info found in knowledge base"
        except Exception as e:
            return f"Knowledge error: {str(e)}"
    
    def register(self, name, description, function):
        """Register a skill"""
        self.skills[name] = Skill(name, description, function)
    
    def execute(self, skill_name, *args):
        """Execute a skill"""
        if skill_name in self.skills:
            return self.skills[skill_name].execute(*args)
        return f"Skill {skill_name} not found"
    
    def list_skills(self):
        """List all skills"""
        return {name: skill.description for name, skill in self.skills.items()}
    
    def match_skill(self, query):
        """Match a query to a skill"""
        query = query.lower().strip()
        
        # Direct skill commands
        for name in self.skills:
            if query == name or query.startswith(name + " "):
                return name
        
        return None


def test():
    """Test skills"""
    sm = SkillsManager()
    
    print("Skills:", sm.list_skills())
    print("\nTime:", sm.execute('time'))
    print("\nWeather:", sm.execute('weather', 'Mumbai'))


if __name__ == "__main__":
    test()