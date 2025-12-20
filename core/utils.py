import uuid
import json
import os

def generate_id():
    return str(uuid.uuid4())[:8]

def create_manifest(export_path, video_data_list):
    """
    Creates a manifest file for Gemlogin automation.
    video_data_list: list of dicts with keys: 'file_path', 'language', 'title', 'id'
    """
    manifest_path = os.path.join(export_path, "gemlogin_manifest.json")
    
    manifest = {
        "project_name": "Paji Video Export",
        "created_at": str(os.path.getctime(export_path) if os.path.exists(export_path) else ""),
        "videos": video_data_list
    }
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=4, ensure_ascii=False)
    return manifest_path

CONFIG_PATH = "config.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(data):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

PRESETS_PATH = "cover_presets.json"

def load_cover_presets():
    if os.path.exists(PRESETS_PATH):
        try:
            with open(PRESETS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cover_presets(data):
    try:
        with open(PRESETS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving presets: {e}")

# Settings Presets
SETTINGS_PRESETS_PATH = "settings_presets.json"

def load_settings_presets():
    """Load all saved settings presets."""
    if os.path.exists(SETTINGS_PRESETS_PATH):
        try:
            with open(SETTINGS_PRESETS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings_presets(data):
    """Save settings presets to file."""
    try:
        with open(SETTINGS_PRESETS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving settings presets: {e}")

def save_settings_preset(name, settings):
    """Save a single preset by name."""
    presets = load_settings_presets()
    presets[name] = settings
    save_settings_presets(presets)

def delete_settings_preset(name):
    """Delete a preset by name."""
    presets = load_settings_presets()
    if name in presets:
        del presets[name]
        save_settings_presets(presets)
        return True
    return False

