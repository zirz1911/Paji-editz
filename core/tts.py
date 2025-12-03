import os
import wave
import base64
import requests
import json

# Gemini Voices (Single-speaker)
GEMINI_VOICES = [
    "Puck", "Charon", "Kore", "Fenrir", "Aoede", 
    "Zephyr", "Leda", "Orus", "Callirrhoe", "Autonoe", 
    "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", 
    "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar", 
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", 
    "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"
]

def verify_api_key(api_key):
    """
    Verifies the Gemini API key by attempting to list models via REST.
    Returns (True, "Valid") or (False, ErrorMessage).
    """
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            return True, "API Key is valid!"
        else:
            return False, f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

def save_wave_file(filename, pcm_data, channels=1, rate=24000, sample_width=2):
    """Saves PCM data to a WAV file."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)

def generate_audio(text, language, output_path, voice="Puck", api_key=None):
    """
    Generates audio using Gemini API Speech Generation (REST API).
    """
    print(f"Generating audio with Gemini API (REST), voice: {voice}")
    
    if not api_key:
        print("Error: API Key is required for Gemini TTS.")
        return None

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [{
                "parts": [{"text": text}]
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice
                        }
                    }
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"Gemini API Error {response.status_code}: {response.text}")
            return None
            
        result = response.json()
        
        # Extract audio data
        # Structure: candidates[0].content.parts[0].inlineData.data
        if "candidates" in result and result["candidates"]:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                if parts and "inlineData" in parts[0]:
                    data_base64 = parts[0]["inlineData"]["data"]
                    pcm_data = base64.b64decode(data_base64)
                    
                    # Save as WAV
                    # If output_path ends in .mp3, we save as .wav first then rename/convert?
                    # The system expects a file at output_path.
                    # Since we are writing raw WAV, let's write to output_path but ensure it has a wav header.
                    # If the filename is .mp3, it will be a WAV file named .mp3. 
                    # Most players/ffmpeg handle this fine (sniffing format).
                    
                    save_wave_file(output_path, pcm_data)
                    return output_path
        
        print(f"Unexpected response format: {result}")
        return None
            
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None

