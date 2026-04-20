#!/usr/bin/env python3
"""
JARVIS - Main Orchestrator
The Brain + Voice = Your AI Assistant
"""

from jarvis.agent import GeneralPurposeAgent
from jarvis.llm import JARVISBrain
from jarvis.voice import VoiceInput, VoiceOutput


class JARVIS:
    def __init__(self):
        print("🧠 Initializing JARVIS agent...")
        self.agent = GeneralPurposeAgent()

        print("🗣️ Initializing voice output...")
        self.voice = VoiceOutput()

        print("🎤 Initializing voice input...")
        self.voice_in = VoiceInput()

        self.running = False
        self.name = "JARVIS"

    def start(self):
        """Start JARVIS"""
        self.running = True
        self.voice.speak(f"Good morning, sir. {self.name} is online.")
        print("\n" + "=" * 50)
        print("  🤖 JARVIS - Ready")
        print("=" * 50)
        print("Commands:")
        print("  voice   - Speak to JARVIS")
        print("  chat    - Type chat mode")
        print("  test    - Test all systems")
        print("  exit    - Quit")
        print("=" * 50 + "\n")

    def process(self, user_input):
        """Process user input and respond"""
        response = self.agent.process(user_input)

        self.voice.speak(response)

        return response

    def listen_mode(self):
        """Voice command mode"""
        print("\n🎤 Voice Mode - Say something (or 'exit' to quit)")
        print("Tip: Speak clearly into your microphone\n")

        while self.running:
            try:
                # Simple input for now - in production use proper STT
                user_input = input("You: ")
                if user_input.lower() in ["exit", "quit"]:
                    break

                if user_input.strip():
                    response = self.process(user_input)
                    print(f"JARVIS: {response}\n")

            except KeyboardInterrupt:
                break

        self.voice.speak("Returning to command mode.")

    def chat_mode(self):
        """Text chat mode"""
        print("\n💬 Chat Mode - Type 'exit' to quit\n")

        while self.running:
            try:
                user_input = input("You: ")
                if user_input.lower() in ["exit", "quit"]:
                    break

                if user_input.strip():
                    response = self.agent.process(user_input)
                    print(f"JARVIS: {response}\n")

            except KeyboardInterrupt:
                break

        self.voice.speak("Returning to command mode.")

    def test_systems(self):
        """Test all systems"""
        print("\n🧪 Testing Systems...\n")

        # Test agent
        print("1. Agent: ", end="")
        response = self.agent.process("Say 'online' in one word.")
        if response:
            print(f"✓ Working: {response}")
        else:
            print("✗ Failed")

        # Test voice
        print("2. Voice: ", end="")
        self.voice.speak("Testing.")
        print("✓ Speaking")

        print("\n🧪 All systems operational, sir.")

    def run(self):
        """Main run loop"""
        self.start()

        while self.running:
            try:
                cmd = input("Command> ").strip().lower()

                if cmd in ["exit", "quit", "q"]:
                    self.running = False
                    self.voice.speak("Disengaging. Have a good day, sir.")
                    break
                elif cmd in ["voice", "v"]:
                    self.listen_mode()
                elif cmd in ["chat", "c"]:
                    self.chat_mode()
                elif cmd in ["test", "t"]:
                    self.test_systems()
                elif cmd in ["help", "h", ""]:
                    print("Commands: voice, chat, test, exit")
                else:
                    response = self.process(cmd)
                    print(f"JARVIS: {response}\n")

            except KeyboardInterrupt:
                self.running = False
                print("\n\nGoodbye, sir.")


def main():
    """Entry point"""
    jarvis = JARVIS()
    jarvis.run()


if __name__ == "__main__":
    main()
