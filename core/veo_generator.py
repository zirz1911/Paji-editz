"""
Veo 3.0 Video Generator Module
Generates AI news anchor videos using Google's Veo 3.0 Fast API.
"""
import os
import time
import requests
import json
import tempfile
import base64


# Veo 3.0 Fast model (for generation)
VEO_MODEL = "veo-3.0-fast-generate-001"
# Veo 3.1 Preview model (for extension - 3.0 doesn't support extension)
VEO_MODEL_EXTEND = "veo-3.1-generate-preview"
VEO_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Supported aspect ratios
ASPECT_RATIOS = {
    "16:9": "16:9",  # Landscape
    "9:16": "9:16",  # Portrait
}


def generate_news_anchor_prompt(script, language_code="en"):
    """
    Generates a Veo prompt for creating a news anchor video.
    
    Args:
        script: The script/text the news anchor should speak
        language_code: Language code (e.g., 'en', 'th', 'ja')
    
    Returns:
        A formatted prompt string for Veo
    """
    # Map language codes to language names for better prompts
    language_names = {
        "en": "English",
        "th": "Thai",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "ru": "Russian",
        "id": "Indonesian",
        "vi": "Vietnamese",
    }
    
    lang_name = language_names.get(language_code, "English")
    
    # Truncate script to reduce chances of triggering safety filters
    # Use only first 100 characters as context
    script_preview = script[:100] if script else ""
    
    # Create a professional news anchor prompt with EXTREME SPEED speaking
    prompt = f"""A {lang_name}-speaking news anchor SPEED-READING breaking news in TV studio.
TRIPLE SPEED talking. 400 words per minute. Fastest human speech possible.
Mouth moves EXTREMELY FAST like fast-forwarded video. Auctioneer-style rapid-fire delivery.
NO PAUSES. NO BREAKS. Continuous machine-gun speech. Racing through words nonstop.
Intense urgent expression. They speed-read: "{script_preview}"
Time-critical emergency broadcast. Hyper-accelerated speech throughout entire video.
Modern studio, blue graphics."""
    
    return prompt


def encode_image_to_base64(image_path):
    """
    Encodes an image file to base64 string.
    
    Args:
        image_path: Path to the image file
    
    Returns:
        base64 encoded string
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path):
    """
    Gets the MIME type of an image based on extension.
    """
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_types.get(ext, "image/jpeg")


def start_video_generation(prompt, aspect_ratio, api_key, resolution="720p", reference_image=None):
    """
    Starts a video generation request with Veo 3.0 Fast API.
    
    Args:
        prompt: Text prompt for video generation
        aspect_ratio: "16:9" or "9:16"
        api_key: Gemini API key
        resolution: Video resolution (default "720p")
        reference_image: Optional path to reference image for consistent appearance
    
    Returns:
        operation_name: The operation name for polling, or None on error
    """
    url = f"{VEO_BASE_URL}/models/{VEO_MODEL}:predictLongRunning?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    instance = {
        "prompt": prompt
    }
    
    # Add reference image if provided
    if reference_image and os.path.exists(reference_image):
        image_data = encode_image_to_base64(reference_image)
        mime_type = get_image_mime_type(reference_image)
        instance["image"] = {
            "bytesBase64Encoded": image_data,
            "mimeType": mime_type
        }
        print(f"Using reference image: {reference_image}")
    
    payload = {
        "instances": [instance],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "resolution": resolution
        }
    }
    
    # Only add personGeneration when NOT using reference image
    # Using allow_all with reference image is not supported
    if not reference_image:
        payload["parameters"]["personGeneration"] = "allow_all"
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"Veo API Error {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        operation_name = result.get("name")
        return operation_name
        
    except Exception as e:
        print(f"Veo API Error: {e}")
        return None


def poll_operation(operation_name, api_key, timeout=300, poll_interval=10):
    """
    Polls an operation until it's complete or times out.
    
    Args:
        operation_name: The operation name from start_video_generation
        api_key: Gemini API key
        timeout: Maximum time to wait in seconds (default 300 = 5 minutes)
        poll_interval: Time between polls in seconds (default 10)
    
    Returns:
        dict: The final response with video URI, or None on error/timeout
    """
    url = f"{VEO_BASE_URL}/{operation_name}?key={api_key}"
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"Veo API Timeout after {timeout} seconds")
            return None
        
        try:
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"Veo Poll Error {response.status_code}: {response.text}")
                return None
            
            result = response.json()
            
            if result.get("done"):
                return result
            
            print(f"Waiting for video generation... ({int(elapsed)}s)")
            time.sleep(poll_interval)
            
        except Exception as e:
            print(f"Veo Poll Error: {e}")
            return None


def start_video_extension(video_uri, prompt, aspect_ratio, api_key, resolution="720p"):
    """
    Starts a video extension request with Veo API.
    Extends a previously generated video with new content.
    
    Args:
        video_uri: URI of the video to extend (from previous generation)
        prompt: Text prompt for the extension content
        aspect_ratio: "16:9" or "9:16"
        api_key: Gemini API key
        resolution: Video resolution (default "720p")
    
    Returns:
        operation_name: The operation name for polling, or None on error
    """
    # Use Veo 3.1 for extension (3.0 doesn't support it)
    url = f"{VEO_BASE_URL}/models/{VEO_MODEL_EXTEND}:predictLongRunning?key={api_key}"
    
    print(f"[Extension] Using model: {VEO_MODEL_EXTEND}")
    print(f"[Extension] Video URI: {video_uri[:80]}...")
    print(f"[Extension] Prompt: {prompt[:100]}...")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "instances": [{
            "prompt": prompt,
            "video": {
                "uri": video_uri
            }
        }],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "resolution": resolution
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"Veo Extension API Error {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        operation_name = result.get("name")
        print(f"[Extension] Operation started: {operation_name}")
        return operation_name
        
    except Exception as e:
        print(f"Veo Extension API Error: {e}")
        return None


def download_video(video_uri, output_path, api_key):
    """
    Downloads a generated video from Veo.
    
    Args:
        video_uri: URI of the video to download
        output_path: Local path to save the video
        api_key: Gemini API key
    
    Returns:
        output_path on success, None on failure
    """
    try:
        headers = {
            "x-goog-api-key": api_key
        }
        
        response = requests.get(video_uri, headers=headers, stream=True, allow_redirects=True)
        
        if response.status_code != 200:
            print(f"Download Error {response.status_code}")
            return None
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return output_path
        
    except Exception as e:
        print(f"Download Error: {e}")
        return None


def extend_video(video_uri, prompt, aspect_ratio, api_key, output_path, logger=None):
    """
    Extends a previously generated Veo video with new content.
    
    Args:
        video_uri: URI of the video to extend (from previous generation)
        prompt: Text prompt for the extension content
        aspect_ratio: "16:9" or "9:16"
        api_key: Gemini API key
        output_path: Path to save the extended video
        logger: Optional logger function
    
    Returns:
        dict with 'output_path' and 'video_uri' on success, None on failure
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    log(f"Extending video with Veo 3.0 Fast...")
    log(f"Extension prompt: {prompt[:100]}...")
    
    # Start extension
    operation_name = start_video_extension(video_uri, prompt, aspect_ratio, api_key)
    if not operation_name:
        log("Failed to start video extension")
        return None
    
    log(f"Extension started. Operation: {operation_name}")
    
    # Poll for completion
    result = poll_operation(operation_name, api_key, timeout=600)
    if not result:
        log("Video extension failed or timed out")
        return None
    
    # Extract video URI
    try:
        response_data = result.get("response", {})
        generated_samples = response_data.get("generateVideoResponse", {}).get("generatedSamples", [])
        
        if not generated_samples:
            log("No video generated in response")
            return None
        
        new_video_uri = generated_samples[0].get("video", {}).get("uri")
        if not new_video_uri:
            log("No video URI in response")
            return None
        
        log(f"Downloading extended video...")
        
        # Download video
        downloaded = download_video(new_video_uri, output_path, api_key)
        if not downloaded:
            log("Failed to download extended video")
            return None
        
        log(f"Extended video saved to: {output_path}")
        return {"output_path": output_path, "video_uri": new_video_uri}
        
    except Exception as e:
        log(f"Error processing extension response: {e}")
        return None


def generate_video(prompt, aspect_ratio, api_key, output_path, logger=None, reference_image=None):
    """
    Generates a single video using Veo 3.0 Fast.
    
    Args:
        prompt: Text prompt for video generation
        aspect_ratio: "16:9" or "9:16"
        api_key: Gemini API key
        output_path: Path to save the generated video
        logger: Optional logger function
        reference_image: Optional path to reference image for consistent appearance
    
    Returns:
        dict with 'output_path' and 'video_uri' on success, None on failure
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    log(f"Starting video generation with Veo 3.0 Fast...")
    log(f"Aspect Ratio: {aspect_ratio}")
    if reference_image:
        log(f"Using reference image: {reference_image}")
    
    # Start generation
    operation_name = start_video_generation(prompt, aspect_ratio, api_key, reference_image=reference_image)
    if not operation_name:
        log("Failed to start video generation")
        return None
    
    log(f"Generation started. Operation: {operation_name}")
    
    # Poll for completion
    result = poll_operation(operation_name, api_key, timeout=600)
    if not result:
        log("Video generation failed or timed out")
        return None
    
    # Extract video URI
    try:
        response_data = result.get("response", {})
        
        # Debug: Log full response structure
        log(f"Response keys: {list(result.keys())}")
        if response_data:
            log(f"Response data keys: {list(response_data.keys())}")
        
        generate_response = response_data.get("generateVideoResponse", {})
        generated_samples = generate_response.get("generatedSamples", [])
        
        # Check for RAI (content moderation) filter
        rai_count = generate_response.get("raiMediaFilteredCount", 0)
        rai_reasons = generate_response.get("raiMediaFilteredReasons", [])
        
        if rai_count > 0 or rai_reasons:
            log(f"⚠️ Content was filtered by safety system!")
            for reason in rai_reasons:
                log(f"Reason: {reason[:200]}...")
            log("Try modifying your script or using a different reference image.")
            return None
        
        if not generated_samples:
            # Check for error in response
            if "error" in result:
                log(f"API Error: {result['error']}")
            log(f"Full response: {str(result)[:500]}")
            log("No video generated in response")
            return None
        
        video_uri = generated_samples[0].get("video", {}).get("uri")
        if not video_uri:
            log("No video URI in response")
            return None
        
        log(f"Downloading video...")
        
        # Download video
        downloaded = download_video(video_uri, output_path, api_key)
        if not downloaded:
            log("Failed to download video")
            return None
        
        log(f"Video saved to: {output_path}")
        return {"output_path": output_path, "video_uri": video_uri}
        
    except Exception as e:
        log(f"Error processing response: {e}")
        return None


def generate_news_anchor_video(script, aspect_ratio, language_code, api_key, output_path, logger=None, reference_image=None):
    """
    Generates a news anchor video from a script.
    
    Args:
        script: The script/text the news anchor should speak
        aspect_ratio: "16:9" or "9:16"
        language_code: Language code (e.g., 'en', 'th')
        api_key: Gemini API key
        output_path: Path to save the generated video
        logger: Optional logger function
        reference_image: Optional path to reference image for consistent anchor appearance
    
    Returns:
        dict with 'output_path' and 'video_uri' on success, None on failure
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    log(f"Generating news anchor video...")
    log(f"Language: {language_code}")
    log(f"Script: {script[:100]}...")
    if reference_image:
        log(f"Reference Image: {reference_image}")
    
    # Generate prompt
    prompt = generate_news_anchor_prompt(script, language_code)
    log(f"Prompt generated")
    
    # Generate video
    result = generate_video(prompt, aspect_ratio, api_key, output_path, logger, reference_image=reference_image)
    
    return result


def verify_veo_access(api_key):
    """
    Verifies if the API key has access to Veo models.
    
    Args:
        api_key: Gemini API key
    
    Returns:
        (bool, str): (success, message)
    """
    try:
        url = f"{VEO_BASE_URL}/models?key={api_key}"
        response = requests.get(url)
        
        if response.status_code != 200:
            return False, f"API Error {response.status_code}"
        
        result = response.json()
        models = result.get("models", [])
        
        # Check if Veo model is available
        veo_available = any("veo" in m.get("name", "").lower() for m in models)
        
        if veo_available:
            return True, "Veo access verified!"
        else:
            return False, "Veo models not available for this API key"
            
    except Exception as e:
        return False, str(e)
