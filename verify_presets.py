import os
import json
from core.utils import save_cover_presets, load_cover_presets

def test_presets():
    print("Starting Preset Verification...")
    
    # 1. Test Save
    test_data = {
        "Test Preset": {
            "font_size": "100",
            "text_color": "#FF0000",
            "border_color": "#000000",
            "border_width": "5",
            "text_pos": [0.5, 0.5]
        }
    }
    
    print("Saving preset...")
    save_cover_presets(test_data)
    
    if os.path.exists("cover_presets.json"):
        print("cover_presets.json created.")
    else:
        print("Failed to create cover_presets.json")
        return

    # 2. Test Load
    print("Loading presets...")
    loaded_data = load_cover_presets()
    
    if "Test Preset" in loaded_data:
        print("Preset loaded successfully.")
        print(f"Data: {loaded_data['Test Preset']}")
        
        if loaded_data["Test Preset"]["font_size"] == "100":
            print("Data integrity check: PASS")
        else:
            print("Data integrity check: FAIL")
    else:
        print("Failed to load preset.")

    # Cleanup
    # os.remove("cover_presets.json") # Keep it for manual inspection if needed

if __name__ == "__main__":
    test_presets()
