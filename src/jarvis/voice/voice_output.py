#!/usr/bin/env python3
"""
JARVIS Voice Output Module
Uses macOS built-in TTS - free and excellent quality
"""

import subprocess
import os
import threading

class VoiceOutput:
    def __init__(self):
        self.voice = "Daniel"  # British male voice
        self.rate = 180  # Words per minute
        
    def speak(self, text, async_mode=True):
        """Speak text using macOS TTS"""
        if async_mode:
            thread = threading.Thread(target=self._speak_sync, args=(text,))
            thread.start()
        else:
            self._speak_sync(text)
    
    def _speak_sync(self, text):
        """Synchronous speak"""
        # Use say command with British voice
        subprocess.run(
            ['say', '-v', self.voice, '-r', str(self.rate), text],
            capture_output=True
        )
    
    def set_voice(self, voice_name):
        """Change voice"""
        available = self.get_voices()
        if voice_name in available:
            self.voice = voice_name
            return f"Voice set to {voice_name}"
        return f"Voice not found. Available: {', '.join(available)}"
    
    def get_voices(self):
        """List available voices"""
        result = subprocess.run(
            ['say', '--voices'],
            capture_output=True,
            text=True
        )
        voices = []
        for line in result.stdout.split('\n'):
            if line.strip():
                parts = line.split()
                if parts:
                    voices.append(parts[0])
        return voices


def test_voice():
    """Test voice output"""
    voice = VoiceOutput()
    print("Available voices:", voice.get_voices()[:5], "...")
    voice.speak("Good evening, sir. Systems are online and ready.")
    print("Spoke successfully!")


if __name__ == "__main__":
    test_voice()