import os
from core.tts import generate_audio

API_KEY = "AIzaSyCSDdeS_n1h431IPtCe0gQzsJKEsokiG1k"
VOICE = "Puck"
TEXT = "Hello, this is a test."
OUTPUT = "debug_output.wav"

print("Starting TTS Debug...")
result = generate_audio(TEXT, "en", OUTPUT, voice=VOICE, api_key=API_KEY)

if result:
    print(f"Success! Saved to {result}")
else:
    print("Failed to generate audio.")
