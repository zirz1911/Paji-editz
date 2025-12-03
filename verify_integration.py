import os
import shutil
from core.image_gen import draw_text_on_image
from core.translation import translate_text

# Mocking the workflow
def test_integration():
    print("Starting Integration Verification...")
    
    # 1. Setup Mock Data
    lang_code = "th"
    lang_name = "Thai"
    base_name = "test_video_th"
    export_dir = "test_export"
    lang_dir = os.path.join(export_dir, lang_name)
    os.makedirs(lang_dir, exist_ok=True)
    
    # Mock Cover Settings (as if saved from GUI)
    cover_settings = {
        "topic": "This is a test topic",
        "image_path": "test_frame.jpg", # Assuming this exists from previous tests
        "style": {
            "font_size": 60,
            "color": "#FFFFFF",
            "border_color": "#000000",
            "border_width": 4,
            "position": (0.5, 0.5),
            "anchor": "mm"
        }
    }
    
    # Check if base frame exists
    if not os.path.exists(cover_settings["image_path"]):
        print(f"Error: {cover_settings['image_path']} not found. Please run previous verification scripts first.")
        # Create a dummy one
        from PIL import Image
        img = Image.new('RGB', (1280, 720), color = 'blue')
        img.save(cover_settings["image_path"])
        print("Created dummy base frame.")

    # 2. Simulate Process Loop
    print(f"[{lang_name}] Simulating export process...")
    
    # ... (Video generation skipped) ...
    
    # Cover Generation Step
    print(f"[{lang_name}] Generating cover image...")
    try:
        # Translate Topic (Mock API call or real if key exists, let's just mock for speed/cost if possible, 
        # but we want to verify logic. Let's use the real function but handle error if no key)
        
        # We need an API key. If not in config, we skip translation verification or mock it.
        # Let's just use the topic as is if translation fails, or mock the translation function.
        
        topic = cover_settings.get("topic", "")
        translated_topic = f"[Translated] {topic}" # Mock translation
        
        cover_path = os.path.join(lang_dir, f"{base_name}.jpg")
        
        style = cover_settings.get("style", {}).copy()
        base_image_path = cover_settings.get("image_path")
        
        if base_image_path and os.path.exists(base_image_path):
            draw_text_on_image(base_image_path, translated_topic, cover_path, style)
            print(f"[{lang_name}] Cover generated: {cover_path}")
            
            if os.path.exists(cover_path):
                print("Verification SUCCESS: Cover file exists.")
            else:
                print("Verification FAILED: Cover file not found.")
        else:
            print(f"[{lang_name}] Cover generation failed: Base image not found")
            
    except Exception as e:
        print(f"[{lang_name}] Cover generation error: {e}")

if __name__ == "__main__":
    test_integration()
