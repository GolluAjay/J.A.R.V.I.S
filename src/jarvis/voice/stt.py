#!/usr/bin/env python3
"""
macOS-oriented audio capture helper (sox-based).

Renamed from a duplicate ``VoiceInput`` type to ``MacSpeechRecorder`` so it
does not clash with ``jarvis.voice.voice_input.VoiceInput``.
"""

import subprocess
import tempfile
import os
import sys

class MacSpeechRecorder:
    def __init__(self):
        self.sample_rate = 16000
        self.language = "en-US"
        
    def listen(self, duration=5):
        """Listen and transcribe speech using macOS speech recognition"""
        print("🎤 Listening...")
        
        # Method 1: Use Apple Speech Recognition (macOS built-in)
        # This runs in background and outputs to file
        with tempfile.NamedTemporaryFile(mode='w', suffix='', delete=False) as f:
            output_file = f.name + ".txt"
        
        try:
            # Use macOS say command to test, but for recognition we need a different approach
            # Let's use a simple approach: record audio then process
            result = self._record_and_transcribe(duration)
            return result
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _record_and_transcribe(self, duration=5):
        """Record audio and prepare for transcription"""
        # Create temp file for recording
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_wav = f.name
        
        try:
            # Record using sox
            print(f"Recording {duration} seconds...")
            subprocess.run([
                'sox', '-d', temp_wav,
                '-r', '16000', '-c', '1',
                'trim', '0', str(duration)
            ], capture_output=True, timeout=duration+5)
            
            # Check if recording exists
            if os.path.getsize(temp_wav) > 1000:
                print("Audio captured!")
                # Return the file for processing
                return temp_wav
            else:
                return None
                
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            return None
        finally:
            # Cleanup handled by caller
            pass
    
    def test_microphone(self):
        """Test if microphone is working"""
        # Try to list input devices
        result = subprocess.run(
            ['sox', '--devices'],
            capture_output=True,
            text=True
        )
        if 'input' in result.stdout.lower():
            return True
        return False


def test_stt():
    """Test voice input"""
    stt = MacSpeechRecorder()
    print("Testing voice input...")
    
    if stt.test_microphone():
        print("✓ Microphone detected")
        print("  To use: say command and JARVIS will listen")
    else:
        print("✗ No microphone found (or permission denied)")
        print("  Grant microphone access in System Settings > Privacy")


if __name__ == "__main__":
    test_stt()