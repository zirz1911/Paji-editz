import os
import wave
import base64
import requests
import json
import subprocess

# Gemini Voices (Single-speaker)
GEMINI_VOICES = [
    "Puck", "Charon", "Kore", "Fenrir", "Aoede", 
    "Zephyr", "Leda", "Orus", "Callirrhoe", "Autonoe", 
    "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", 
    "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar", 
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", 
    "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"
]

# Speech speed options
SPEECH_SPEEDS = {
    "Very Slow (0.7x)": 0.7,
    "Slow (0.85x)": 0.85,
    "Normal (1.0x)": 1.0,
    "Fast (1.15x)": 1.15,
    "Very Fast (1.3x)": 1.3
}

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

def generate_audio(text, language, output_path, voice="Puck", api_key=None, speech_speed=1.0, voice_prompt=""):
    """
    Generates audio using Gemini API Speech Generation (REST API).
    speech_speed: 0.5 to 2.0 (1.0 = normal speed)
    voice_prompt: Custom instructions for tone/style (e.g. "speak cheerfully", "speak slowly and calmly")
    """
    print(f"Generating audio with Gemini API (REST), voice: {voice}, speed: {speech_speed}x")
    
    if not api_key:
        print("Error: API Key is required for Gemini TTS.")
        return None

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Combine voice prompt with actual text
        if voice_prompt and voice_prompt.strip():
            full_text = f"[{voice_prompt.strip()}] {text}"
            print(f"Voice prompt: {voice_prompt}")
        else:
            full_text = text
        
        payload = {
            "contents": [{
                "parts": [{"text": full_text}]
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
                    
                    # Save as temporary WAV first
                    if speech_speed != 1.0:
                        import tempfile
                        temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                        temp_wav.close()
                        save_wave_file(temp_wav.name, pcm_data)
                        
                        # Use FFmpeg to adjust speed with atempo filter
                        # atempo only supports 0.5 to 2.0
                        speed = max(0.5, min(2.0, speech_speed))
                        
                        cmd = [
                            'ffmpeg', '-y',
                            '-i', temp_wav.name,
                            '-af', f'atempo={speed}',
                            output_path
                        ]
                        subprocess.run(cmd, capture_output=True)
                        
                        # Cleanup temp file
                        try:
                            os.remove(temp_wav.name)
                        except:
                            pass
                    else:
                        save_wave_file(output_path, pcm_data)
                    
                    return output_path
        
        print(f"Unexpected response format: {result}")
        return None
            
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None
