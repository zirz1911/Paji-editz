import os
import json
from core.image_gen import draw_text_on_image
from core.video import extract_frame

def test_wrapping():
    print("Starting Text Wrapping Verification...")
    
    # 1. Extract Frame if needed
    if not os.path.exists("test_frame.jpg"):
        print("Extracting frame...")
        if os.path.exists("debug_video.mp4"):
            extract_frame("debug_video.mp4", "test_frame.jpg")
        else:
            print("No video found. Please provide test_frame.jpg or debug_video.mp4")
            return

    # 2. Test Long Text
    long_text = "This is a very long text that should definitely wrap to multiple lines because it is too long for the image width."
    output_path = "test_wrap.jpg"
    
    style = {
        "font_size": 80,
        "color": "#FFFF00",
        "border_color": "#000000",
        "border_width": 4,
        "position": "center",
        "anchor": "mm"
    }
    
    print(f"Generating image with text: '{long_text}'")
    result = draw_text_on_image("test_frame.jpg", long_text, output_path, style)
    
    if result and os.path.exists(output_path):
        print(f"Success! Check {output_path} to verify wrapping visually.")
    else:
        print("Failed to generate image.")

if __name__ == "__main__":
    test_wrapping()
