import os
import shutil
import random
from core.image_gen import draw_text_on_image

# Mocking the workflow
def test_integration_v2():
    print("Starting Integration Verification V2 (Flat & Random)...")
    
    # 1. Setup Mock Data
    lang_code = "th"
    lang_name = "Thai"
    title = "Test Video Title"
    export_dir = "test_export_v2"
    os.makedirs(export_dir, exist_ok=True)
    
    # Mock Cover Settings
    cover_settings = {
        "topic": "This is a test topic",
        "image_path": "test_frame.jpg",
        "style": {
            "font_size": 60,
            "color": "#FFFFFF",
            "border_color": "#000000",
            "border_width": 4,
            "position": (0.5, 0.5),
            "anchor": "mm"
        }
    }
    
    # Ensure base frame exists
    if not os.path.exists(cover_settings["image_path"]):
        from PIL import Image
        img = Image.new('RGB', (1280, 720), color = 'blue')
        img.save(cover_settings["image_path"])
    
    # 2. Simulate Naming Logic
    rand_num = random.randint(10000, 99999)
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    safe_title = safe_title.replace(" ", "_")
    base_name = f"{safe_title}_{lang_name}_{rand_num}"
    
    print(f"Generated Base Name: {base_name}")
    
    # 3. Simulate Cover Generation
    # Use export_dir directly (Flat structure)
    cover_path = os.path.join(export_dir, f"{base_name}.jpg")
    
    print(f"[{lang_name}] Generating cover image at {cover_path}...")
    
    try:
        topic = cover_settings.get("topic", "")
        translated_topic = f"[Translated] {topic}"
        
        style = cover_settings.get("style", {}).copy()
        base_image_path = cover_settings.get("image_path")
        
        if base_image_path and os.path.exists(base_image_path):
            draw_text_on_image(base_image_path, translated_topic, cover_path, style)
            print(f"[{lang_name}] Cover generated: {cover_path}")
            
            if os.path.exists(cover_path):
                print("Verification SUCCESS: Cover file exists in flat directory.")
            else:
                print("Verification FAILED: Cover file not found.")
        else:
            print("Failed: Base image not found")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_integration_v2()
