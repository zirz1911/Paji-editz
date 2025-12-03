import os
import json
from core.translation import translate_text
from core.image_gen import draw_text_on_image
from core.video import extract_frame

def test_backend():
    print("Starting Backend Verification...")
    
    # Load Config for API Key
    api_key = None
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            config = json.load(f)
            api_key = config.get("api_key")
            
    if not api_key:
        print("WARNING: No API Key found in config.json. Skipping translation test.")
    else:
        print("Testing Translation...")
        text = "Hello World"
        translated = translate_text(text, "th", api_key)
        print(f"Original: {text}, Translated (TH): {translated}")
        if translated:
            print("Translation: PASS")
        else:
            print("Translation: FAIL")

    # Test Frame Extraction
    print("\nTesting Frame Extraction...")
    video_path = "debug_video.mp4"
    if not os.path.exists(video_path):
        print(f"Error: {video_path} not found. Skipping frame extraction test.")
    else:
        frame_path = "test_frame.jpg"
        result = extract_frame(video_path, frame_path, time_ratio=0.5)
        if result and os.path.exists(frame_path):
            print("Frame Extraction: PASS")
        else:
            print("Frame Extraction: FAIL")
            
    # Test Image Generation
    print("\nTesting Image Generation...")
    if os.path.exists("test_frame.jpg"):
        output_path = "test_cover.jpg"
        style = {
            "font_size": 80,
            "color": "#FF0000",
            "border_color": "#FFFFFF",
            "border_width": 4,
            "position": (100, 100),
            "anchor": "mm"
        }
        
        # We need to pass the image path we just extracted
        result = draw_text_on_image("test_frame.jpg", "Test Cover", output_path, style)
        if result and os.path.exists(output_path):
            print("Image Generation: PASS")
        else:
            print("Image Generation: FAIL")
    else:
        print("Skipping Image Generation test (no frame extracted).")

if __name__ == "__main__":
    test_backend()
