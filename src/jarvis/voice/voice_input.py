#!/usr/bin/env python3
"""
JARVIS Voice Input Module
Records and processes voice commands
"""

import subprocess
import tempfile
import os
import wave
from collections import deque

class VoiceInput:
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 1024
        self.silence_threshold = 500  # Adjust based on testing
        self.max_silence_duration = 2.0  # seconds
        
    def listen_for_command(self, timeout=5):
        """Listen for voice command (simple version using speech recognition)"""
        print("🎤 Listening...")
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_file = f.name
        
        try:
            # Record using sox (5 second max)
            cmd = [
                'sox', '-d', temp_file,
                '-r', str(self.sample_rate),
                '-c', str(self.channels),
                '-t', 'wav',
                'trim', '0', str(timeout)
            ]
            subprocess.run(cmd, capture_output=True)
            
            # Check if file has audio
            if os.path.getsize(temp_file) > 1000:
                # Return file path for STT processing
                return temp_file
            else:
                return None
                
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def record_audio(self, duration=3):
        """Record audio for specified duration"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_file = f.name
        
        subprocess.run([
            'sox', '-d', temp_file,
            '-r', '16000', '-c', '1',
            'trim', '0', str(duration)
        ], capture_output=True)
        
        return temp_file
    
    def audio_to_text(self, audio_file):
        """Convert audio to text using Ollama (if it supports audio) or return placeholder"""
        # Note: Ollama doesn't support audio input directly
        # In production, use whisper.cpp or API
        print(f"📄 Audio file: {audio_file}")
        return "Voice command captured"


def test_microphone():
    """Test microphone input"""
    print("Testing microphone...")
    mic = VoiceInput()
    
    # Check if sox can list input devices
    result = subprocess.run(
        ['sox', '--device-list', 'input'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("Available input devices:")
        print(result.stdout)
    else:
        print("Could not list devices (this is normal on macOS)")


if __name__ == "__main__":
    test_microphone()