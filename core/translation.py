import requests
import json

def translate_text(text, target_lang_code, api_key):
    """
    Translates text using Gemini API.
    """
    if not api_key:
        print("Error: API Key is required for translation.")
        return None

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        prompt = f"Translate the following text to {target_lang_code}. Only return the translated text, nothing else.\n\nText: {text}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"Gemini API Error {response.status_code}: {response.text}")
            return None
            
        result = response.json()
        
        if "candidates" in result and result["candidates"]:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                translated_text = candidate["content"]["parts"][0]["text"].strip()
                return translated_text
        
        return None
            
    except Exception as e:
        print(f"Translation Error: {e}")
        return None
