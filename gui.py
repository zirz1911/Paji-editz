import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
import os
import threading
import shutil
import subprocess
from PIL import Image, ImageTk
from core.tts import generate_audio, verify_api_key, GEMINI_VOICES, SPEECH_SPEEDS
from core.subtitles import generate_subtitles, save_srt
from core.video import merge_audio_video, burn_subtitles, extract_frame, burn_subtitle_image, get_audio_duration, create_slideshow_video, overlay_logo, create_images_to_videos, concatenate_videos, insert_overlay_with_fade, burn_subtitles_for_news
from core.utils import generate_id, create_manifest, load_config, save_config, load_cover_presets, save_cover_presets, load_settings_presets, save_settings_preset, delete_settings_preset
from core.veo_generator import generate_news_anchor_video, verify_veo_access, ASPECT_RATIOS, extend_video
from core.translation import translate_text
from core.image_gen import draw_text_on_image
import random
import time

def get_system_fonts():
    """Get list of available system fonts using fc-list"""
    try:
        result = subprocess.run(['fc-list', ':', 'family'], capture_output=True, text=True)
        fonts = set()
        for line in result.stdout.strip().split('\n'):
            # Take the first font name if there are aliases (comma separated)
            font_name = line.split(',')[0].strip()
            # Skip fonts starting with '.' (internal system fonts)
            if font_name and not font_name.startswith('.'):
                fonts.add(font_name)
        return sorted(list(fonts))
    except Exception as e:
        print(f"Error getting system fonts: {e}")
        return ["Arial", "Helvetica", "Times New Roman", "Noto Sans", "Noto Sans Thai"]

SUPPORTED_LANGUAGES = {
    "English (US)": "en",
    "Thai": "th",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese (Simplified)": "zh",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Indonesian": "id",
    "Vietnamese": "vi"
}

class VideoEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Paji Video Editor")
        self.geometry("1100x800")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Data
        self.source_video_path = None
        self.image_folder_path = None  # For slideshow mode
        self.languages_data = {} # {lang_code: {text_widget, title_entry}}
        self.cover_settings = None # Stores settings from Cover Generator
        
        # Load Settings
        self.settings = load_config()
        self.subtitle_margin_v = self.settings.get("margin_v", 20)
        
        # Logo settings
        self.logo_path = self.settings.get("logo_path", None)
        self.logo_position = self.settings.get("logo_position", {"x": 50, "y": 50})  # Default top-left
        self.logo_scale = self.settings.get("logo_scale", 0.15)  # Default 15% of video width

        self.create_sidebar()
        self.create_main_area()
        
        # Bind close event to save settings
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.save_current_settings()
        self.destroy()

    def save_current_settings(self):
        # Get logo position from entries
        try:
            logo_x = int(self.logo_x_entry.get())
        except:
            logo_x = self.logo_position.get("x", 50)
        try:
            logo_y = int(self.logo_y_entry.get())
        except:
            logo_y = self.logo_position.get("y", 50)
        self.logo_position = {"x": logo_x, "y": logo_y}
        
        # Get logo scale from entry (percentage to decimal)
        try:
            self.logo_scale = int(self.logo_scale_entry.get()) / 100.0
        except:
            pass
        
        # Get subtitle margin from entry
        try:
            self.subtitle_margin_v = int(self.sub_margin_entry.get())
        except:
            pass
        
        data = {
            "api_key": self.api_key_entry.get().strip(),
            "font_name": self.font_name_entry.get(),
            "font_size": self.font_size_entry.get(),
            "font_color": self.selected_color,
            "subtitle_mode": self.sub_mode_var.get(),
            "margin_v": self.subtitle_margin_v,
            "voice": self.voice_var.get(),
            "speech_speed": self.speech_speed_var.get(),
            "voice_prompt": self.voice_prompt_entry.get(),
            "audio_mode": self.audio_mode_var.get(),
            "music_path": self.music_path,
            "image_duration": self.image_duration_entry.get(),
            "border_enabled": self.border_enabled_var.get(),
            "bg_enabled": self.bg_enabled_var.get(),
            "bg_color": self.selected_bg_color,
            "logo_enabled": self.logo_enabled_var.get(),
            "logo_path": self.logo_path,
            "logo_position": self.logo_position,
            "logo_scale": self.logo_scale
        }
        save_config(data)

    def create_sidebar(self):
        # Use scrollable frame for sidebar to handle overflow
        self.sidebar_frame = ctk.CTkScrollableFrame(self, width=350, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        self.app_title_label = ctk.CTkLabel(self.sidebar_frame, text="Paji Editor", font=ctk.CTkFont(size=24, weight="bold"))
        self.app_title_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Settings Preset Section
        self.preset_label = ctk.CTkLabel(self.sidebar_frame, text="Settings Preset", font=ctk.CTkFont(weight="bold"))
        self.preset_label.grid(row=1, column=0, padx=20, pady=(10, 5))
        
        self.preset_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.preset_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        # Load presets
        self.settings_presets = load_settings_presets()
        preset_names = list(self.settings_presets.keys())
        
        self.preset_var = ctk.StringVar(value="Select Preset")
        self.preset_dropdown = ctk.CTkOptionMenu(
            self.preset_frame, 
            variable=self.preset_var, 
            values=["Select Preset"] + preset_names,
            command=self.load_preset,
            width=180
        )
        self.preset_dropdown.pack(side="left", padx=(0, 5))
        
        self.save_preset_btn = ctk.CTkButton(self.preset_frame, text="💾", width=35, command=self.save_preset_dialog)
        self.save_preset_btn.pack(side="left", padx=2)
        
        self.delete_preset_btn = ctk.CTkButton(self.preset_frame, text="🗑️", width=35, fg_color="red", hover_color="darkred", command=self.delete_current_preset)
        self.delete_preset_btn.pack(side="left", padx=2)

        # Source Mode Selection
        self.source_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Source Mode", font=ctk.CTkFont(weight="bold"))
        self.source_mode_label.grid(row=3, column=0, padx=20, pady=(10, 5))

        self.source_mode_var = ctk.StringVar(value="video")
        
        self.video_mode_radio = ctk.CTkRadioButton(self.sidebar_frame, text="Video File", variable=self.source_mode_var, value="video", command=self.toggle_source_mode)
        self.video_mode_radio.grid(row=4, column=0, padx=20, pady=2, sticky="w")
        
        self.image_mode_radio = ctk.CTkRadioButton(self.sidebar_frame, text="Media Folder (Slideshow)", variable=self.source_mode_var, value="image_folder", command=self.toggle_source_mode)
        self.image_mode_radio.grid(row=5, column=0, padx=20, pady=2, sticky="w")

        # Video Selection Frame
        self.video_source_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.video_source_frame.grid(row=6, column=0, padx=20, pady=5, sticky="ew")
        
        self.select_video_btn = ctk.CTkButton(self.video_source_frame, text="Select Source Video", command=self.select_video)
        self.select_video_btn.pack(pady=2)
        
        self.video_label = ctk.CTkLabel(self.video_source_frame, text="No video selected", wraplength=280, font=ctk.CTkFont(size=10))
        self.video_label.pack(pady=2)

        # Image/Video Folder Selection Frame
        self.image_source_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.image_source_frame.grid(row=6, column=0, padx=20, pady=5, sticky="ew")
        
        self.select_folder_btn = ctk.CTkButton(self.image_source_frame, text="Select Media Folder", command=self.select_image_folder)
        self.select_folder_btn.pack(pady=2)
        
        self.folder_label = ctk.CTkLabel(self.image_source_frame, text="No folder selected", wraplength=200, font=ctk.CTkFont(size=10))
        self.folder_label.pack(pady=2)
        
        # Image Duration Setting
        self.image_duration_label = ctk.CTkLabel(self.image_source_frame, text="Seconds per Image:", font=ctk.CTkFont(size=11))
        self.image_duration_label.pack(pady=(5, 0))
        
        self.image_duration_entry = ctk.CTkEntry(self.image_source_frame, placeholder_text="3", width=80)
        self.image_duration_entry.insert(0, self.settings.get("image_duration", "3"))
        self.image_duration_entry.pack(pady=2)
        
        # Initially show video mode
        self.toggle_source_mode()

        # TTS Settings
        self.tts_label = ctk.CTkLabel(self.sidebar_frame, text="Gemini TTS Settings", font=ctk.CTkFont(weight="bold"))
        self.tts_label.grid(row=7, column=0, padx=20, pady=(10, 5))

        # API Key Input
        self.api_key_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Gemini API Key", show="*")
        self.api_key_entry.grid(row=8, column=0, padx=20, pady=5)
        if "api_key" in self.settings:
            self.api_key_entry.insert(0, self.settings["api_key"])

        # Voice Selection
        self.voice_var = ctk.StringVar(value=self.settings.get("voice", GEMINI_VOICES[0]))
        self.voice_dropdown = ctk.CTkOptionMenu(self.sidebar_frame, variable=self.voice_var, values=GEMINI_VOICES)
        self.voice_dropdown.grid(row=9, column=0, padx=20, pady=5)
        
        # Speech Speed Selection
        self.speech_speed_var = ctk.StringVar(value=self.settings.get("speech_speed", "Normal (1.0x)"))
        self.speech_speed_dropdown = ctk.CTkOptionMenu(self.sidebar_frame, variable=self.speech_speed_var, values=list(SPEECH_SPEEDS.keys()))
        self.speech_speed_dropdown.grid(row=10, column=0, padx=20, pady=5)
        
        # Voice Prompt (Tone/Style)
        self.voice_prompt_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Voice prompt (e.g. cheerful, calm)")
        self.voice_prompt_entry.grid(row=11, column=0, padx=20, pady=5)
        if "voice_prompt" in self.settings:
            self.voice_prompt_entry.insert(0, self.settings["voice_prompt"])

        # Check API Button
        self.check_api_btn = ctk.CTkButton(self.sidebar_frame, text="Check API Status", command=self.check_api, width=100, fg_color="gray")
        self.check_api_btn.grid(row=12, column=0, padx=20, pady=5)

        # Audio/Video Mode
        self.audio_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Audio/Video Mode", font=ctk.CTkFont(weight="bold"))
        self.audio_mode_label.grid(row=13, column=0, padx=20, pady=(10, 5))

        self.audio_mode_var = ctk.StringVar(value=self.settings.get("audio_mode", "trim"))

        self.trim_radio = ctk.CTkRadioButton(self.sidebar_frame, text="Trim Video to Audio", variable=self.audio_mode_var, value="trim", command=self.toggle_music_options)
        self.trim_radio.grid(row=14, column=0, padx=20, pady=2, sticky="w")

        self.music_radio = ctk.CTkRadioButton(self.sidebar_frame, text="Add Background Music", variable=self.audio_mode_var, value="bg_music", command=self.toggle_music_options)
        self.music_radio.grid(row=15, column=0, padx=20, pady=2, sticky="w")

        # Music Selection
        self.music_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.music_frame.grid(row=16, column=0, padx=20, pady=5)

        self.select_music_btn = ctk.CTkButton(self.music_frame, text="Select Music File", command=self.select_music, width=150)
        self.select_music_btn.pack(pady=2)

        self.music_label = ctk.CTkLabel(self.music_frame, text="No music selected", font=ctk.CTkFont(size=10))
        self.music_label.pack(pady=2)

        self.music_path = self.settings.get("music_path", "")
        if self.music_path:
            self.music_label.configure(text=os.path.basename(self.music_path))
            
        self.toggle_music_options()

        # Subtitle Settings
        self.settings_label = ctk.CTkLabel(self.sidebar_frame, text="Subtitle Settings", font=ctk.CTkFont(weight="bold"))
        self.settings_label.grid(row=17, column=0, padx=20, pady=(10, 5))

        # Font Selection Dropdown
        self.system_fonts = get_system_fonts()
        saved_font = self.settings.get("font_name", "Arial")
        self.font_name_var = ctk.StringVar(value=saved_font if saved_font in self.system_fonts else "Arial")
        self.font_name_entry = ctk.CTkComboBox(self.sidebar_frame, values=self.system_fonts, variable=self.font_name_var, width=180)
        self.font_name_entry.grid(row=18, column=0, padx=20, pady=5)

        self.font_size_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Font Size")
        self.font_size_entry.insert(0, self.settings.get("font_size", "75"))
        self.font_size_entry.grid(row=19, column=0, padx=20, pady=5)

        self.color_btn = ctk.CTkButton(self.sidebar_frame, text="Text Color", command=self.pick_color)
        self.color_btn.grid(row=20, column=0, padx=20, pady=5)
        self.selected_color = self.settings.get("font_color", "#FFFFFF")
        self.color_btn.configure(fg_color=self.selected_color, text_color="black" if self.selected_color.lower() > "#aaaaaa" else "white")
        
        # Text Border Option
        self.border_enabled_var = ctk.BooleanVar(value=self.settings.get("border_enabled", True))
        self.border_checkbox = ctk.CTkCheckBox(self.sidebar_frame, text="Text Border (Outline)", variable=self.border_enabled_var)
        self.border_checkbox.grid(row=21, column=0, padx=20, pady=5, sticky="w")
        
        # Text Background Option
        self.bg_enabled_var = ctk.BooleanVar(value=self.settings.get("bg_enabled", False))
        self.bg_checkbox = ctk.CTkCheckBox(self.sidebar_frame, text="Text Background", variable=self.bg_enabled_var, command=self.toggle_bg_color)
        self.bg_checkbox.grid(row=22, column=0, padx=20, pady=5, sticky="w")
        
        self.bg_color_btn = ctk.CTkButton(self.sidebar_frame, text="BG Color", command=self.pick_bg_color, width=100)
        self.bg_color_btn.grid(row=23, column=0, padx=20, pady=2)
        self.selected_bg_color = self.settings.get("bg_color", "#000000")
        self.bg_color_btn.configure(fg_color=self.selected_bg_color, text_color="white" if self.selected_bg_color.lower() < "#888888" else "black")
        self.toggle_bg_color()  # Show/hide based on checkbox
        
        self.sub_mode_var = ctk.StringVar(value=self.settings.get("subtitle_mode", "sentence"))
        self.sub_mode_switch = ctk.CTkSwitch(self.sidebar_frame, text="Word Level Subtitles", variable=self.sub_mode_var, onvalue="word", offvalue="sentence")
        self.sub_mode_switch.grid(row=24, column=0, padx=20, pady=10)

        # Logo & Position Settings (Combined)
        self.logo_pos_label = ctk.CTkLabel(self.sidebar_frame, text="Logo & Position Settings", font=ctk.CTkFont(weight="bold"))
        self.logo_pos_label.grid(row=25, column=0, padx=20, pady=(10, 5))
        
        # Logo Enable
        self.logo_enabled_var = ctk.BooleanVar(value=self.settings.get("logo_enabled", False))
        self.logo_checkbox = ctk.CTkCheckBox(self.sidebar_frame, text="Enable Logo", variable=self.logo_enabled_var, command=self.toggle_logo_options)
        self.logo_checkbox.grid(row=26, column=0, padx=20, pady=5, sticky="w")
        
        # Logo Options Frame (collapsible)
        self.logo_options_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.logo_options_frame.grid(row=27, column=0, padx=20, pady=5, sticky="ew")
        
        # Select Logo Button
        self.select_logo_btn = ctk.CTkButton(self.logo_options_frame, text="Select Logo", command=self.select_logo, width=100)
        self.select_logo_btn.grid(row=0, column=0, columnspan=2, pady=5)
        
        self.logo_file_label = ctk.CTkLabel(self.logo_options_frame, text="No logo selected" if not self.logo_path else os.path.basename(self.logo_path), wraplength=280, font=ctk.CTkFont(size=10))
        self.logo_file_label.grid(row=1, column=0, columnspan=2, pady=2)
        
        # Logo Position X
        self.logo_x_label = ctk.CTkLabel(self.logo_options_frame, text="Logo X:", font=ctk.CTkFont(size=11))
        self.logo_x_label.grid(row=2, column=0, pady=2, sticky="e")
        self.logo_x_entry = ctk.CTkEntry(self.logo_options_frame, width=80, placeholder_text="50")
        self.logo_x_entry.insert(0, str(self.logo_position.get("x", 50)))
        self.logo_x_entry.grid(row=2, column=1, pady=2, padx=5, sticky="w")
        
        # Logo Position Y
        self.logo_y_label = ctk.CTkLabel(self.logo_options_frame, text="Logo Y:", font=ctk.CTkFont(size=11))
        self.logo_y_label.grid(row=3, column=0, pady=2, sticky="e")
        self.logo_y_entry = ctk.CTkEntry(self.logo_options_frame, width=80, placeholder_text="50")
        self.logo_y_entry.insert(0, str(self.logo_position.get("y", 50)))
        self.logo_y_entry.grid(row=3, column=1, pady=2, padx=5, sticky="w")
        
        # Logo Scale (Size)
        self.logo_scale_label = ctk.CTkLabel(self.logo_options_frame, text="Logo Size (%):", font=ctk.CTkFont(size=11))
        self.logo_scale_label.grid(row=4, column=0, pady=2, sticky="e")
        self.logo_scale_entry = ctk.CTkEntry(self.logo_options_frame, width=80, placeholder_text="15")
        self.logo_scale_entry.insert(0, str(int(self.logo_scale * 100)))  # Show as percentage
        self.logo_scale_entry.grid(row=4, column=1, pady=2, padx=5, sticky="w")
        
        # Button Row for Logo
        self.logo_btn_frame = ctk.CTkFrame(self.logo_options_frame, fg_color="transparent")
        self.logo_btn_frame.grid(row=5, column=0, columnspan=2, pady=5)
        
        self.logo_pos_btn = ctk.CTkButton(self.logo_btn_frame, text="Visual Editor", command=self.open_logo_position_editor, fg_color="gray", width=90)
        self.logo_pos_btn.pack(side="left", padx=2)
        
        self.logo_preview_btn = ctk.CTkButton(self.logo_btn_frame, text="Preview", command=self.preview_logo_position, fg_color="orange", width=90)
        self.logo_preview_btn.pack(side="left", padx=2)
        
        # Subtitle Position Section
        self.subtitle_pos_label = ctk.CTkLabel(self.sidebar_frame, text="Subtitle Position", font=ctk.CTkFont(size=12))
        self.subtitle_pos_label.grid(row=28, column=0, padx=20, pady=(10, 5), sticky="w")
        
        self.sub_pos_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.sub_pos_frame.grid(row=29, column=0, padx=20, pady=2, sticky="ew")
        
        self.sub_margin_label = ctk.CTkLabel(self.sub_pos_frame, text="Margin V:", font=ctk.CTkFont(size=11))
        self.sub_margin_label.grid(row=0, column=0, pady=2, sticky="e")
        self.sub_margin_entry = ctk.CTkEntry(self.sub_pos_frame, width=80, placeholder_text="20")
        self.sub_margin_entry.insert(0, str(self.subtitle_margin_v))
        self.sub_margin_entry.grid(row=0, column=1, pady=2, padx=5, sticky="w")
        
        self.pos_btn = ctk.CTkButton(self.sub_pos_frame, text="Visual Editor", command=self.open_position_editor, fg_color="gray", width=100)
        self.pos_btn.grid(row=0, column=2, padx=5, pady=2)
        
        self.toggle_logo_options()  # Show/hide based on checkbox

        # Process Button
        self.process_btn = ctk.CTkButton(self.sidebar_frame, text="Generate & Export", command=self.start_processing, fg_color="green", hover_color="darkgreen")
        self.process_btn.grid(row=30, column=0, padx=20, pady=20)

        # Cover Generator Button
        self.cover_btn = ctk.CTkButton(self.sidebar_frame, text="Cover Generator", command=self.open_cover_generator, fg_color="purple", hover_color="#4a0072")
        self.cover_btn.grid(row=31, column=0, padx=20, pady=10)

        # Images to Videos Button
        self.img_to_vid_btn = ctk.CTkButton(self.sidebar_frame, text="Images to Videos", command=self.start_images_to_videos, fg_color="orange", hover_color="#cc6600")
        self.img_to_vid_btn.grid(row=32, column=0, padx=20, pady=10)



    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1) # Tab view
        self.main_frame.grid_rowconfigure(2, weight=0) # Log window
        
        # Header
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.news_anchor_btn = ctk.CTkButton(self.header_frame, text="📺 News Anchor", command=self.open_news_anchor_generator, fg_color="#2196F3", hover_color="#1976D2", width=130)
        self.news_anchor_btn.pack(side="right", padx=5)
        
        self.add_lang_btn = ctk.CTkButton(self.header_frame, text="+ Add Language", command=self.add_language_dialog)
        self.add_lang_btn.pack(side="right")
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="Languages & Scripts", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.pack(side="left")

        # Tab View
        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Add default languages
        self.add_language_tab("English (US)", "en")
        self.add_language_tab("Thai", "th")
        
        # Log Window
        self.log_frame = ctk.CTkFrame(self.main_frame)
        self.log_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_label = ctk.CTkLabel(self.log_frame, text="Process Logs", font=ctk.CTkFont(size=12, weight="bold"))
        self.log_label.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        
        self.log_textbox = ctk.CTkTextbox(self.log_frame, height=150)
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.log_textbox.configure(state="disabled")

    def log(self, message):
        self.after(0, lambda: self._log_internal(message))

    def _log_internal(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    # ============== Preset Methods ==============
    
    def get_current_settings_for_preset(self):
        """Get current settings as a dictionary for saving as preset."""
        # Get logo position from entries
        try:
            logo_x = int(self.logo_x_entry.get())
        except:
            logo_x = self.logo_position.get("x", 50)
        try:
            logo_y = int(self.logo_y_entry.get())
        except:
            logo_y = self.logo_position.get("y", 50)
        
        # Get logo scale from entry
        try:
            logo_scale = int(self.logo_scale_entry.get()) / 100.0
        except:
            logo_scale = self.logo_scale
        
        # Get subtitle margin
        try:
            margin_v = int(self.sub_margin_entry.get())
        except:
            margin_v = self.subtitle_margin_v
        
        return {
            "font_name": self.font_name_entry.get(),
            "font_size": self.font_size_entry.get(),
            "font_color": self.selected_color,
            "subtitle_mode": self.sub_mode_var.get(),
            "margin_v": margin_v,
            "voice": self.voice_var.get(),
            "speech_speed": self.speech_speed_var.get(),
            "voice_prompt": self.voice_prompt_entry.get(),
            "audio_mode": self.audio_mode_var.get(),
            "image_duration": self.image_duration_entry.get(),
            "border_enabled": self.border_enabled_var.get(),
            "bg_enabled": self.bg_enabled_var.get(),
            "bg_color": self.selected_bg_color,
            "logo_enabled": self.logo_enabled_var.get(),
            "logo_position": {"x": logo_x, "y": logo_y},
            "logo_scale": logo_scale
        }
    
    def apply_settings_from_preset(self, preset_data):
        """Apply settings from a preset."""
        # Voice settings
        if "voice" in preset_data:
            self.voice_var.set(preset_data["voice"])
        if "speech_speed" in preset_data:
            self.speech_speed_var.set(preset_data["speech_speed"])
        if "voice_prompt" in preset_data:
            self.voice_prompt_entry.delete(0, "end")
            self.voice_prompt_entry.insert(0, preset_data["voice_prompt"])
        
        # Audio mode
        if "audio_mode" in preset_data:
            self.audio_mode_var.set(preset_data["audio_mode"])
            self.toggle_music_options()
        
        # Image duration
        if "image_duration" in preset_data:
            self.image_duration_entry.delete(0, "end")
            self.image_duration_entry.insert(0, preset_data["image_duration"])
        
        # Font settings
        if "font_name" in preset_data:
            self.font_name_var.set(preset_data["font_name"])
        if "font_size" in preset_data:
            self.font_size_entry.delete(0, "end")
            self.font_size_entry.insert(0, preset_data["font_size"])
        if "font_color" in preset_data:
            self.selected_color = preset_data["font_color"]
            self.color_btn.configure(fg_color=self.selected_color)
        
        # Border and background
        if "border_enabled" in preset_data:
            self.border_enabled_var.set(preset_data["border_enabled"])
        if "bg_enabled" in preset_data:
            self.bg_enabled_var.set(preset_data["bg_enabled"])
            self.toggle_bg_color()
        if "bg_color" in preset_data:
            self.selected_bg_color = preset_data["bg_color"]
            self.bg_color_btn.configure(fg_color=self.selected_bg_color)
        
        # Subtitle mode and margin
        if "subtitle_mode" in preset_data:
            self.sub_mode_var.set(preset_data["subtitle_mode"])
        if "margin_v" in preset_data:
            self.subtitle_margin_v = preset_data["margin_v"]
            self.sub_margin_entry.delete(0, "end")
            self.sub_margin_entry.insert(0, str(preset_data["margin_v"]))
        
        # Logo settings
        if "logo_enabled" in preset_data:
            self.logo_enabled_var.set(preset_data["logo_enabled"])
            self.toggle_logo_options()
        if "logo_position" in preset_data:
            self.logo_position = preset_data["logo_position"]
            self.logo_x_entry.delete(0, "end")
            self.logo_x_entry.insert(0, str(preset_data["logo_position"].get("x", 50)))
            self.logo_y_entry.delete(0, "end")
            self.logo_y_entry.insert(0, str(preset_data["logo_position"].get("y", 50)))
        if "logo_scale" in preset_data:
            self.logo_scale = preset_data["logo_scale"]
            self.logo_scale_entry.delete(0, "end")
            self.logo_scale_entry.insert(0, str(int(preset_data["logo_scale"] * 100)))
    
    def load_preset(self, preset_name):
        """Load a preset by name."""
        if preset_name == "Select Preset":
            return
        
        self.settings_presets = load_settings_presets()
        if preset_name in self.settings_presets:
            preset_data = self.settings_presets[preset_name]
            self.apply_settings_from_preset(preset_data)
            self.log(f"Loaded preset: {preset_name}")
    
    def save_preset_dialog(self):
        """Open dialog to save current settings as a preset."""
        dialog = ctk.CTkInputDialog(text="Enter preset name:", title="Save Preset")
        preset_name = dialog.get_input()
        
        if preset_name and preset_name.strip():
            preset_name = preset_name.strip()
            settings = self.get_current_settings_for_preset()
            save_settings_preset(preset_name, settings)
            
            # Refresh dropdown
            self.refresh_preset_dropdown()
            self.preset_var.set(preset_name)
            messagebox.showinfo("Success", f"Preset '{preset_name}' saved!")
    
    def delete_current_preset(self):
        """Delete the currently selected preset."""
        preset_name = self.preset_var.get()
        if preset_name == "Select Preset":
            messagebox.showwarning("Warning", "Please select a preset to delete.")
            return
        
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{preset_name}'?")
        if confirm:
            delete_settings_preset(preset_name)
            self.refresh_preset_dropdown()
            self.preset_var.set("Select Preset")
            messagebox.showinfo("Deleted", f"Preset '{preset_name}' deleted.")
    
    def refresh_preset_dropdown(self):
        """Refresh the preset dropdown with current presets."""
        self.settings_presets = load_settings_presets()
        preset_names = list(self.settings_presets.keys())
        self.preset_dropdown.configure(values=["Select Preset"] + preset_names)


    def select_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.mkv *.mov *.avi")])
        if path:
            self.source_video_path = path
            self.video_label.configure(text=os.path.basename(path))

    def toggle_source_mode(self):
        """Toggle between video and image folder source modes."""
        if self.source_mode_var.get() == "video":
            self.video_source_frame.grid()
            self.image_source_frame.grid_remove()
        else:
            self.video_source_frame.grid_remove()
            self.image_source_frame.grid()

    def select_image_folder(self):
        """Select a folder containing images for slideshow."""
        path = filedialog.askdirectory(title="Select Image Folder")
        if path:
            self.image_folder_path = path
            self.folder_label.configure(text=os.path.basename(path))

    def check_api(self):
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("Error", "Please enter an API Key.")
            return
        
        self.check_api_btn.configure(state="disabled", text="Checking...")
        
        def _run_check():
            valid, msg = verify_api_key(api_key)
            self.after(0, lambda: self._check_result(valid, msg))
            
        threading.Thread(target=_run_check).start()

    def _check_result(self, valid, msg):
        self.check_api_btn.configure(state="normal", text="Check API Status")
        if valid:
            messagebox.showinfo("Success", msg)
            self.check_api_btn.configure(fg_color="green")
        else:
            messagebox.showerror("Error", msg)
            self.check_api_btn.configure(fg_color="red")

    def toggle_music_options(self):
        if self.audio_mode_var.get() == "bg_music":
            self.music_frame.grid()
        else:
            self.music_frame.grid_remove()

    def select_music(self):
        path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.aac")])
        if path:
            self.music_path = path
            self.music_label.configure(text=os.path.basename(path))

    def open_position_editor(self):
        # Get source for background frame
        source_path = None
        frame_path = "temp_frame.jpg"
        
        if self.source_mode_var.get() == "video" and self.source_video_path:
            source_path = self.source_video_path
            # Extract frame from video
            if not extract_frame(self.source_video_path, frame_path):
                messagebox.showerror("Error", "Failed to extract frame from video.")
                return
        elif self.source_mode_var.get() == "image_folder" and self.image_folder_path:
            import glob
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.JPEG', '*.PNG', '*.WEBP']:
                files = glob.glob(os.path.join(self.image_folder_path, ext))
                if files:
                    source_path = sorted(files)[0]
                    # Copy image to temp frame
                    import shutil
                    shutil.copy(source_path, frame_path)
                    break
        
        if not source_path:
            messagebox.showerror("Error", "Please select a source video or image folder first.")
            return
            
        editor = ctk.CTkToplevel(self)
        editor.title("Subtitle Position Editor")
        editor.geometry("450x900")
            
        # Load image
        pil_image = Image.open(frame_path)
        # Get original dimensions
        img_width, img_height = pil_image.size
        
        # Scale to 1080x1920 first (video resolution), then resize for preview
        pil_image = pil_image.resize((1080, 1920), Image.Resampling.LANCZOS)
        img_width, img_height = 1080, 1920
        
        # Preview dimensions (9:16 aspect ratio)
        preview_width = 360
        preview_height = 640
        scale = preview_width / img_width  # Same as preview_height / img_height
        new_w, new_h = preview_width, preview_height
        
        pil_image_resized = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        tk_image = ImageTk.PhotoImage(pil_image_resized)
        
        canvas = tk.Canvas(editor, width=new_w, height=new_h, bg="black")
        canvas.pack(pady=10)
        canvas.create_image(0, 0, anchor="nw", image=tk_image)
        
        # Draw subtitle line
        # Initial position based on current margin
        # Margin is from bottom. In canvas y coordinates: height - margin
        # We need to scale the margin too? Yes.
        # Read margin from entry field
        try:
            current_margin = int(self.sub_margin_entry.get())
        except:
            current_margin = self.subtitle_margin_v
        scaled_margin = current_margin * scale
        initial_y = new_h - scaled_margin
        
        # Scale Font Size for Preview
        try:
            user_font_size = int(self.font_size_entry.get())
        except:
            user_font_size = 75
        
        preview_font_size = int(user_font_size * scale)
        # Ensure minimum visible size
        preview_font_size = max(8, preview_font_size)
        
        # Use the font name if available on system, else Arial
        user_font_name = self.font_name_entry.get()
        # Tkinter font tuple
        preview_font = (user_font_name, preview_font_size)
        
        text_item = canvas.create_text(new_w//2, initial_y, text="Subtitle Preview", fill=self.selected_color, font=preview_font, anchor="s")
        line_item = canvas.create_line(0, initial_y, new_w, initial_y, fill="red", dash=(4, 4))
        
        # Margin Label
        margin_label = canvas.create_text(10, initial_y - 10, text=f"Margin: {current_margin}px", fill="red", anchor="w", font=("Arial", 10))
        
        def on_drag(event):
            # Update Y position
            y = event.y
            # Clamp
            y = max(0, min(y, new_h))
            canvas.coords(text_item, new_w//2, y)
            canvas.coords(line_item, 0, y, new_w, y)
            
            # Update Margin Label
            current_margin_px = new_h - y
            current_original_margin = int(current_margin_px / scale)
            canvas.coords(margin_label, 10, y - 10)
            canvas.itemconfigure(margin_label, text=f"Margin: {current_original_margin}px")
            
        canvas.tag_bind(text_item, "<B1-Motion>", on_drag)
        canvas.tag_bind(line_item, "<B1-Motion>", on_drag)
        
        def save():
            # Calculate margin from bottom
            # Get current Y of text (anchor s means Y is bottom of text)
            coords = canvas.coords(text_item)
            current_y = coords[1]
            margin_px = new_h - current_y
            # Scale back to original video size
            original_margin = int(margin_px / scale)
            self.subtitle_margin_v = max(0, original_margin)
            # Update entry field
            self.sub_margin_entry.delete(0, 'end')
            self.sub_margin_entry.insert(0, str(self.subtitle_margin_v))
            print(f"Saved margin: {self.subtitle_margin_v}")
            editor.destroy()
            
        save_btn = ctk.CTkButton(editor, text="Save Position", command=save)
        save_btn.pack(pady=10)
        
        # Keep reference to image
        editor.image = tk_image
        editor.original_pil = pil_image_resized # Store original for reset
        
        def preview_subtitle():
            # 1. Calculate current margin
            coords = canvas.coords(text_item)
            current_y = coords[1]
            margin_px = new_h - current_y
            original_margin = int(margin_px / scale)
            
            # 2. Create dummy subtitle
            preview_srt = "preview.srt"
            with open(preview_srt, 'w', encoding='utf-8') as f:
                f.write("1\n00:00:00,000 --> 00:00:10,000\nSubtitle Preview\n\n")
            
            # 3. Burn into image
            preview_output = "preview_output.jpg"
            font_settings = {
                "Fontname": self.font_name_entry.get(),
                "Fontsize": self.font_size_entry.get(),
                "PrimaryColour": self.selected_color
            }
            
            # We need to run burn on the ORIGINAL extracted frame to match resolution
            # Then resize back for display
            burned_path = burn_subtitle_image(frame_path, preview_srt, font_settings, preview_output, margin_v=original_margin, logger=self.log)
            
            if burned_path and os.path.exists(burned_path):
                # Load and resize
                p_img = Image.open(burned_path)
                p_img_resized = p_img.resize((new_w, new_h))
                p_tk_image = ImageTk.PhotoImage(p_img_resized)
                
                # Update canvas
                canvas.create_image(0, 0, anchor="nw", image=p_tk_image)
                editor.image = p_tk_image # Keep ref
                
                # Hide the drag lines/text temporarily so they don't overlap
                canvas.itemconfigure(text_item, state='hidden')
                canvas.itemconfigure(line_item, state='hidden')
                canvas.itemconfigure(margin_label, state='hidden')
            else:
                messagebox.showerror("Error", "Preview generation failed. Check logs.")

        def reset_preview():
            # Restore original image
            tk_img = ImageTk.PhotoImage(editor.original_pil)
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
            editor.image = tk_img
            
            # Show drag items
            canvas.itemconfigure(text_item, state='normal')
            canvas.itemconfigure(line_item, state='normal')
            canvas.itemconfigure(margin_label, state='normal')
            # Bring to front
            canvas.tag_raise(text_item)
            canvas.tag_raise(line_item)
            canvas.tag_raise(margin_label)

        btn_frame = ctk.CTkFrame(editor, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        preview_btn = ctk.CTkButton(btn_frame, text="Preview (FFmpeg)", command=preview_subtitle, fg_color="blue")
        preview_btn.pack(side="left", padx=5)
        
        reset_btn = ctk.CTkButton(btn_frame, text="Reset", command=reset_preview, fg_color="gray")
        reset_btn.pack(side="left", padx=5)

        save_btn = ctk.CTkButton(btn_frame, text="Save Position", command=save)
        save_btn.pack(side="left", padx=5)

    def pick_color(self):
        color = colorchooser.askcolor(title="Choose Subtitle Color", color=self.selected_color)
        if color[1]:
            self.selected_color = color[1]
            self.color_btn.configure(fg_color=self.selected_color, text_color="black" if self.selected_color.lower() > "#aaaaaa" else "white")

    def toggle_bg_color(self):
        """Show/hide background color button based on checkbox state."""
        if self.bg_enabled_var.get():
            self.bg_color_btn.grid()
        else:
            self.bg_color_btn.grid_remove()

    def pick_bg_color(self):
        """Pick background color for subtitle."""
        color = colorchooser.askcolor(title="Choose Background Color", color=self.selected_bg_color)
        if color[1]:
            self.selected_bg_color = color[1]
            self.bg_color_btn.configure(fg_color=self.selected_bg_color, text_color="white" if self.selected_bg_color.lower() < "#888888" else "black")

    def toggle_logo_options(self):
        """Show/hide logo options based on checkbox state."""
        if self.logo_enabled_var.get():
            self.logo_options_frame.grid()
        else:
            self.logo_options_frame.grid_remove()

    def select_logo(self):
        """Select logo image file."""
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.logo_path = path
            self.logo_file_label.configure(text=os.path.basename(path))

    def open_logo_position_editor(self):
        """Open logo position editor with actual video frame and correctly scaled logo."""
        if not self.logo_path or not os.path.exists(self.logo_path):
            messagebox.showerror("Error", "Please select a logo image first.")
            return
        
        # Get source for background frame
        source_path = None
        if self.source_mode_var.get() == "video" and self.source_video_path:
            source_path = self.source_video_path
        elif self.source_mode_var.get() == "image_folder" and self.image_folder_path:
            import glob
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.JPEG', '*.PNG', '*.WEBP']:
                files = glob.glob(os.path.join(self.image_folder_path, ext))
                if files:
                    source_path = sorted(files)[0]
                    break
        
        if not source_path:
            messagebox.showerror("Error", "Please select a source video or image folder first.")
            return
        
        editor = ctk.CTkToplevel(self)
        editor.title("Logo Position Editor")
        editor.geometry("450x900")
        editor.transient(self)
        editor.grab_set()
        
        # Instructions
        instr_label = ctk.CTkLabel(editor, text="Drag logo to move • Hold Shift for fine movement", font=ctk.CTkFont(size=12))
        instr_label.pack(pady=5)
        
        try:
            from PIL import Image, ImageTk
            import subprocess
            import tempfile
            
            # Extract frame from video or load image
            is_video = source_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))
            
            if is_video:
                temp_frame = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                temp_frame.close()
                cmd = ['ffmpeg', '-y', '-ss', '1', '-i', source_path, '-vframes', '1', 
                       '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
                       temp_frame.name]
                subprocess.run(cmd, capture_output=True)
                bg_img = Image.open(temp_frame.name)
                editor.temp_frame = temp_frame.name  # Store for cleanup
            else:
                bg_img = Image.open(source_path)
                # Scale to 1080x1920
                bg_img = bg_img.resize((1080, 1920), Image.Resampling.LANCZOS)
                editor.temp_frame = None
            
            # Actual video dimensions (reference)
            actual_width = 1080
            actual_height = 1920
            
            # Preview dimensions (scaled down for display)
            preview_width = 360
            preview_height = 640
            
            # Scale factors
            scale_x = preview_width / actual_width
            scale_y = preview_height / actual_height
            
            # Create background for preview
            bg_preview = bg_img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
            editor.bg_tk = ImageTk.PhotoImage(bg_preview)
            
            # Load and scale logo according to logo_scale_entry
            logo_original = Image.open(self.logo_path)
            
            # Get logo scale from entry (percentage of video width)
            try:
                logo_scale_percent = int(self.logo_scale_entry.get())
            except:
                logo_scale_percent = 15
            
            # Calculate actual logo width in video
            actual_logo_width = int(actual_width * logo_scale_percent / 100)
            # Maintain aspect ratio
            logo_orig_w, logo_orig_h = logo_original.size
            actual_logo_height = int(actual_logo_width * logo_orig_h / logo_orig_w)
            
            # Scale logo for preview
            preview_logo_width = int(actual_logo_width * scale_x)
            preview_logo_height = int(actual_logo_height * scale_y)
            preview_logo_width = max(1, preview_logo_width)
            preview_logo_height = max(1, preview_logo_height)
            
            logo_preview = logo_original.resize((preview_logo_width, preview_logo_height), Image.Resampling.LANCZOS)
            editor.logo_tk = ImageTk.PhotoImage(logo_preview)
            
            # Create canvas
            canvas_frame = ctk.CTkFrame(editor)
            canvas_frame.pack(pady=10)
            
            canvas = tk.Canvas(canvas_frame, width=preview_width, height=preview_height, bg="black")
            canvas.pack()
            
            # Draw background
            canvas.create_image(0, 0, image=editor.bg_tk, anchor="nw")
            
            # Read initial position from entry fields
            try:
                init_x_actual = int(self.logo_x_entry.get())
            except:
                init_x_actual = self.logo_position.get("x", 50)
            try:
                init_y_actual = int(self.logo_y_entry.get())
            except:
                init_y_actual = self.logo_position.get("y", 50)
            
            init_x = int(init_x_actual * scale_x)
            init_y = int(init_y_actual * scale_y)
            
            logo_item = canvas.create_image(init_x, init_y, image=editor.logo_tk, anchor="nw")
            
            # Position label
            pos_label = ctk.CTkLabel(editor, text=f"Position: X={init_x_actual}, Y={init_y_actual} | Size: {logo_scale_percent}%")
            pos_label.pack(pady=5)
            
            # Drag state
            editor.drag_data = {"x": 0, "y": 0, "item": logo_item}
            editor.shift_pressed = False
            
            def on_key_press(event):
                if event.keysym == "Shift_L" or event.keysym == "Shift_R":
                    editor.shift_pressed = True
            
            def on_key_release(event):
                if event.keysym == "Shift_L" or event.keysym == "Shift_R":
                    editor.shift_pressed = False
            
            def on_drag_start(event):
                editor.drag_data["x"] = event.x
                editor.drag_data["y"] = event.y
            
            def on_drag_motion(event):
                delta_x = event.x - editor.drag_data["x"]
                delta_y = event.y - editor.drag_data["y"]
                
                # Fine movement with shift
                if editor.shift_pressed:
                    delta_x = delta_x // 5
                    delta_y = delta_y // 5
                
                canvas.move(logo_item, delta_x, delta_y)
                editor.drag_data["x"] = event.x
                editor.drag_data["y"] = event.y
                
                # Update position display
                coords = canvas.coords(logo_item)
                actual_x = int(coords[0] / scale_x)
                actual_y = int(coords[1] / scale_y)
                pos_label.configure(text=f"Position: X={actual_x}, Y={actual_y} | Size: {logo_scale_percent}%")
            
            canvas.tag_bind(logo_item, "<Button-1>", on_drag_start)
            canvas.tag_bind(logo_item, "<B1-Motion>", on_drag_motion)
            
            editor.bind("<KeyPress>", on_key_press)
            editor.bind("<KeyRelease>", on_key_release)
            editor.focus_set()
            
            def save_position():
                coords = canvas.coords(logo_item)
                new_x = int(coords[0] / scale_x)
                new_y = int(coords[1] / scale_y)
                self.logo_position = {"x": new_x, "y": new_y}
                # Update entry fields
                self.logo_x_entry.delete(0, 'end')
                self.logo_x_entry.insert(0, str(new_x))
                self.logo_y_entry.delete(0, 'end')
                self.logo_y_entry.insert(0, str(new_y))
                cleanup_and_close()
            
            def cleanup_and_close():
                if editor.temp_frame and os.path.exists(editor.temp_frame):
                    try:
                        os.remove(editor.temp_frame)
                    except:
                        pass
                editor.destroy()
            
            btn_frame = ctk.CTkFrame(editor, fg_color="transparent")
            btn_frame.pack(pady=10)
            
            save_btn = ctk.CTkButton(btn_frame, text="Save Position", command=save_position, fg_color="green")
            save_btn.pack(side="left", padx=5)
            
            cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=cleanup_and_close)
            cancel_btn.pack(side="left", padx=5)
            
            editor.protocol("WM_DELETE_WINDOW", cleanup_and_close)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")
            editor.destroy()

    def preview_logo_position(self):
        """Generate FFmpeg preview of logo position on actual video frame."""
        if not self.logo_path or not os.path.exists(self.logo_path):
            messagebox.showerror("Error", "Please select a logo image first.")
            return
        
        # Get source for preview
        source_path = None
        if self.source_mode_var.get() == "video" and self.source_video_path:
            source_path = self.source_video_path
        elif self.source_mode_var.get() == "image_folder" and self.image_folder_path:
            # Find first image in folder
            import glob
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.JPEG', '*.PNG', '*.WEBP']:
                files = glob.glob(os.path.join(self.image_folder_path, ext))
                if files:
                    source_path = sorted(files)[0]
                    break
        
        if not source_path:
            messagebox.showerror("Error", "Please select a source video or image folder first.")
            return
        
        try:
            import subprocess
            import tempfile
            
            # Create temporary output file
            temp_preview = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_preview.close()
            
            # Read position from entry fields
            try:
                x = int(self.logo_x_entry.get())
            except:
                x = self.logo_position.get("x", 50)
            try:
                y = int(self.logo_y_entry.get())
            except:
                y = self.logo_position.get("y", 50)
            
            # Read scale from entry field (percentage to actual width)
            try:
                scale_percent = int(self.logo_scale_entry.get())
                logo_width = int(1080 * scale_percent / 100)  # 1080 is video width
            except:
                logo_width = 162  # Default ~15% of 1080
            
            # Determine if source is video or image
            is_video = source_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))
            
            if is_video:
                # Extract frame and overlay logo
                cmd = [
                    'ffmpeg', '-y',
                    '-ss', '1',  # Seek to 1 second
                    '-i', source_path,
                    '-i', self.logo_path,
                    '-filter_complex', f'[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[bg];[1:v]scale={logo_width}:-1[logo];[bg][logo]overlay={x}:{y}',
                    '-frames:v', '1',
                    temp_preview.name
                ]
            else:
                # Image source
                cmd = [
                    'ffmpeg', '-y',
                    '-i', source_path,
                    '-i', self.logo_path,
                    '-filter_complex', f'[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[bg];[1:v]scale={logo_width}:-1[logo];[bg][logo]overlay={x}:{y}',
                    '-frames:v', '1',
                    temp_preview.name
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                messagebox.showerror("Error", f"FFmpeg error: {result.stderr[:500]}")
                return
            
            # Show preview in popup
            preview_window = ctk.CTkToplevel(self)
            try:
                scale_val = int(self.logo_scale_entry.get())
            except:
                scale_val = 15
            preview_window.title(f"Logo Preview - Position: ({x}, {y}) Size: {scale_val}%")
            preview_window.geometry("400x750")
            preview_window.transient(self)
            
            # Load and display preview image
            from PIL import Image, ImageTk
            preview_img = Image.open(temp_preview.name)
            preview_img = preview_img.resize((360, 640), Image.Resampling.LANCZOS)
            preview_tk = ImageTk.PhotoImage(preview_img)
            
            preview_window.preview_img = preview_tk  # Keep reference
            
            img_label = tk.Label(preview_window, image=preview_tk)
            img_label.pack(pady=10)
            
            pos_label = ctk.CTkLabel(preview_window, text=f"Logo Position: X={x}, Y={y}, Size={scale_val}%")
            pos_label.pack(pady=5)
            
            close_btn = ctk.CTkButton(preview_window, text="Close", command=preview_window.destroy)
            close_btn.pack(pady=10)
            
            # Cleanup temp file after window closes
            def on_close():
                try:
                    os.remove(temp_preview.name)
                except:
                    pass
                preview_window.destroy()
            
            preview_window.protocol("WM_DELETE_WINDOW", on_close)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate preview: {e}")

    def add_language_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Language")
        dialog.geometry("300x150")
        
        label = ctk.CTkLabel(dialog, text="Select Language:")
        label.pack(pady=10)
        
        lang_var = ctk.StringVar(value="English (US)")
        combobox = ctk.CTkComboBox(dialog, values=list(SUPPORTED_LANGUAGES.keys()), variable=lang_var)
        combobox.pack(pady=10)
        
        def add():
            lang_name = lang_var.get()
            lang_code = SUPPORTED_LANGUAGES.get(lang_name, "en")
            self.add_language_tab(lang_name, lang_code)
            dialog.destroy()
            
        btn = ctk.CTkButton(dialog, text="Add", command=add)
        btn.pack(pady=10)

    def add_language_tab(self, name, code):
        if name in self.languages_data:
            return
            
        self.tab_view.add(name)
        tab = self.tab_view.tab(name)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Title Input
        title_entry = ctk.CTkEntry(tab, placeholder_text=f"Video Title for {name}")
        title_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        # Remove Button
        remove_btn = ctk.CTkButton(tab, text="Remove", width=60, fg_color="red", hover_color="darkred", command=lambda n=name: self.remove_language_tab(n))
        remove_btn.grid(row=0, column=1, padx=(0, 10), pady=(10, 5))
        
        # Script Input
        text_box = ctk.CTkTextbox(tab)
        text_box.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
        
        # Placeholder Logic
        placeholder_text = f"Enter script for {name} here..."
        
        def on_focus_in(event):
            if text_box.get("0.0", "end-1c") == placeholder_text:
                text_box.delete("0.0", "end")
                text_box.configure(text_color=("black", "white"))

        def on_focus_out(event):
            if not text_box.get("0.0", "end-1c").strip():
                text_box.insert("0.0", placeholder_text)
                text_box.configure(text_color="gray")

        text_box.insert("0.0", placeholder_text)
        text_box.configure(text_color="gray")
        text_box.bind("<FocusIn>", on_focus_in)
        text_box.bind("<FocusOut>", on_focus_out)
        
        self.languages_data[name] = {
            "code": code,
            "title_entry": title_entry,
            "text_box": text_box,
            "placeholder": placeholder_text # Store to check against later
        }

    def remove_language_tab(self, name):
        if name in self.languages_data:
            self.tab_view.delete(name)
            del self.languages_data[name]

    def start_processing(self):
        # Validate based on source mode
        if self.source_mode_var.get() == "video":
            if not self.source_video_path:
                messagebox.showerror("Error", "Please select a source video first.")
                return
        else:  # image_folder mode
            if not self.image_folder_path:
                messagebox.showerror("Error", "Please select an image folder first.")
                return
            
        export_dir = filedialog.askdirectory(title="Select Export Folder")
        if not export_dir:
            return
            
        self.process_btn.configure(state="disabled", text="Processing...")
        
        api_key = self.api_key_entry.get().strip()
        
        # Collect data
        tasks = []
        for lang_name, data in self.languages_data.items():
            script = data["text_box"].get("0.0", "end").strip()
            # Ignore if it's just the placeholder
            if script == data["placeholder"]:
                script = ""
                
            title = data["title_entry"].get().strip()
            if not title:
                title = f"Video_{lang_name}"
            
            # Now allow tasks without script (will skip audio generation)
            tasks.append({
                "name": lang_name,
                "code": data["code"],
                "script": script,  # Can be empty
                "title": title
            })
        
        if not tasks:
            messagebox.showerror("Error", "Please add at least one language tab.")
            self.process_btn.configure(state="normal", text="Generate & Export")
            return

        # Save settings before processing
        self.save_current_settings()

        # Start thread
        thread = threading.Thread(target=self.process_tasks, args=(tasks, export_dir, api_key))
        thread.start()

    def process_tasks(self, tasks, export_dir, api_key):
        try:
            manifest_data = []
            
            for task in tasks:
                lang_code = task["code"]
                lang_name = task["name"]
                script = task["script"]
                title = task["title"]
                
                # Create language folder
                lang_dir = os.path.join(export_dir, lang_name)
                os.makedirs(lang_dir, exist_ok=True)
                
                # Generate random ID/Number
                rand_num = random.randint(10000, 99999)
                
                # Sanitize title for filename
                safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                safe_title = safe_title.replace(" ", "_")
                
                base_name = f"{safe_title}_{lang_name}_{rand_num}"
                
                # Paths
                audio_path = os.path.join(lang_dir, f"{base_name}.mp3")
                video_merged_path = os.path.join(lang_dir, f"{base_name}_merged.mp4")
                srt_path = os.path.join(lang_dir, f"{base_name}.srt")
                final_video_path = os.path.join(lang_dir, f"{base_name}.mp4") # Removed _final for cleaner name
                
                # Check if script is provided
                has_script = script and script.strip()
                audio_file = None
                audio_duration = None
                
                if has_script:
                    # 1. Generate Audio
                    self.log(f"[{lang_name}] Generating audio...")
                    speech_speed = SPEECH_SPEEDS.get(self.speech_speed_var.get(), 1.0)
                    voice_prompt = self.voice_prompt_entry.get().strip()
                    audio_file = generate_audio(
                        script, 
                        lang_code, 
                        audio_path, 
                        voice=self.voice_var.get(),
                        api_key=api_key,
                        speech_speed=speech_speed,
                        voice_prompt=voice_prompt
                    )
                    if not audio_file:
                        self.log(f"[{lang_name}] Failed to generate audio")
                        continue
                    audio_duration = get_audio_duration(audio_path)
                else:
                    self.log(f"[{lang_name}] No script provided, skipping audio generation...")
                    # Get default duration from image duration setting
                    try:
                        audio_duration = float(self.image_duration_entry.get())
                    except:
                        audio_duration = 5.0
                
                # 2. Create/Merge Video based on source mode
                source_mode = self.source_mode_var.get()
                
                if source_mode == "image_folder":
                    # Create slideshow from images
                    self.log(f"[{lang_name}] Creating slideshow from images...")
                    if not audio_duration:
                        self.log(f"[{lang_name}] Failed to get duration")
                        continue
                    
                    slideshow_path = os.path.join(lang_dir, f"{base_name}_slideshow.mp4")
                    # Get image duration setting
                    try:
                        image_duration_sec = float(self.image_duration_entry.get())
                    except:
                        image_duration_sec = 3.0
                    
                    slideshow_file = create_slideshow_video(
                        self.image_folder_path,
                        audio_duration,
                        slideshow_path,
                        transition_duration=0.5,
                        image_duration=image_duration_sec
                    )
                    if not slideshow_file:
                        self.log(f"[{lang_name}] Failed to create slideshow")
                        continue
                    
                    if has_script and audio_file:
                        # Merge slideshow with audio
                        self.log(f"[{lang_name}] Merging slideshow with audio...")
                        merged_file = merge_audio_video(
                            slideshow_path, 
                            audio_path, 
                            video_merged_path,
                            mode="trim",  # Always trim for slideshow since it's already exact length
                            music_path=self.music_path if self.audio_mode_var.get() == "bg_music" else None
                        )
                        # Cleanup slideshow temp file
                        if os.path.exists(slideshow_path):
                            os.remove(slideshow_path)
                    else:
                        # No audio - just use slideshow as merged file
                        merged_file = slideshow_path
                        video_merged_path = slideshow_path
                else:
                    # Original video mode
                    if has_script and audio_file:
                        self.log(f"[{lang_name}] Merging video with audio...")
                        merged_file = merge_audio_video(
                            self.source_video_path, 
                            audio_path, 
                            video_merged_path,
                            mode=self.audio_mode_var.get(),
                            music_path=self.music_path
                        )
                    else:
                        # No audio - just copy video
                        self.log(f"[{lang_name}] Processing video (no audio)...")
                        import subprocess
                        cmd = [
                            'ffmpeg', '-y',
                            '-i', self.source_video_path,
                            '-t', str(audio_duration),
                            '-c:v', 'copy',
                            '-an',  # No audio
                            video_merged_path
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        merged_file = video_merged_path if result.returncode == 0 else None
                
                if not merged_file:
                    self.log(f"[{lang_name}] Failed to process video")
                    continue

                # 3. Generate Subtitles (skip for Thai language or no audio)
                if not has_script or not audio_file:
                    self.log(f"[{lang_name}] Skipping subtitles (no script/audio)...")
                    subtitled_file = merged_file
                elif lang_code == 'th':
                    self.log(f"[{lang_name}] Skipping subtitles for Thai language...")
                    subtitled_file = merged_file  # Use merged file directly without subtitles
                else:
                    self.log(f"[{lang_name}] Generating subtitles...")
                    subs = generate_subtitles(audio_path, language=lang_code, mode=self.sub_mode_var.get())
                    save_srt(subs, srt_path)
                    
                    # 4. Burn Subtitles
                    self.log(f"[{lang_name}] Burning subtitles...")
                    font_settings = {
                        "Fontname": self.font_name_entry.get(),
                        "Fontsize": self.font_size_entry.get(),
                        "PrimaryColour": self.selected_color,
                        "BorderEnabled": self.border_enabled_var.get(),
                        "BackgroundEnabled": self.bg_enabled_var.get(),
                        "BackgroundColour": self.selected_bg_color
                    }
                    subtitle_output = os.path.join(lang_dir, f"{base_name}_subtitled.mp4")
                    subtitled_file = burn_subtitles(merged_file, srt_path, font_settings, subtitle_output, margin_v=self.subtitle_margin_v, logger=self.log)
                    
                    # Cleanup intermediate merged file
                    if os.path.exists(merged_file):
                        os.remove(merged_file)
                    
                    if not subtitled_file:
                        self.log(f"[{lang_name}] Failed to burn subtitles")
                        continue
                
                # 5. Overlay Logo (if enabled)
                if self.logo_enabled_var.get() and self.logo_path and os.path.exists(self.logo_path):
                    self.log(f"[{lang_name}] Adding logo overlay...")
                    final_file = overlay_logo(
                        subtitled_file,
                        self.logo_path,
                        final_video_path,
                        position=self.logo_position,
                        logo_scale=self.logo_scale,
                        logger=self.log
                    )
                    # Cleanup subtitled file
                    if os.path.exists(subtitled_file):
                        os.remove(subtitled_file)
                else:
                    # No logo, just rename/move subtitled file
                    import shutil
                    shutil.move(subtitled_file, final_video_path)
                    final_file = final_video_path
                
                if final_file:
                    self.log(f"[{lang_name}] Completed: {os.path.basename(final_file)}") 
                    manifest_data.append({
                        "id": rand_num,
                        "language": lang_name,
                        "title": title,
                        "file_path": final_file
                    })

                    # 5. Generate Cover Image (if enabled)
                    if self.cover_settings:
                        self.log(f"[{lang_name}] Generating cover image...")
                        try:
                            # Translate Topic
                            topic = self.cover_settings.get("topic", "")
                            if topic:
                                translated_topic = translate_text(topic, lang_code, api_key)
                            else:
                                translated_topic = title # Fallback to title if no topic
                            
                            cover_path = os.path.join(lang_dir, f"{base_name}.jpg")
                            
                            # Prepare Style
                            style = self.cover_settings.get("style", {}).copy()
                            # Ensure we use the saved frame
                            base_image_path = self.cover_settings.get("image_path")
                            
                            if base_image_path and os.path.exists(base_image_path):
                                draw_text_on_image(base_image_path, translated_topic, cover_path, style)
                                self.log(f"[{lang_name}] Cover generated: {os.path.basename(cover_path)}")
                            else:
                                self.log(f"[{lang_name}] Cover generation failed: Base image not found")
                        except Exception as e:
                            self.log(f"[{lang_name}] Cover generation error: {e}")
            create_manifest(export_dir, manifest_data)
            self.log("All tasks completed successfully!")
            
            self.after(0, lambda: messagebox.showinfo("Success", "Export completed successfully!"))
            
        except Exception as e:
            self.log(f"Error: {e}")
            print(f"Error in processing: {e}")
            self.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {e}"))
        finally:
            self.after(0, lambda: self.process_btn.configure(state="normal", text="Generate & Export"))

    def open_cover_generator(self):
        if not self.source_video_path:
            messagebox.showerror("Error", "Please select a source video first.")
            return
            
        CoverGeneratorWindow(self)

    def start_images_to_videos(self):
        """Open dialog to convert individual images to separate videos."""
        # Select input folder
        input_folder = filedialog.askdirectory(title="Select Image Folder")
        if not input_folder:
            return
        
        # Select output folder
        output_folder = filedialog.askdirectory(title="Select Output Folder for Videos")
        if not output_folder:
            return
        
        # Get duration from settings
        try:
            duration = float(self.image_duration_entry.get())
        except:
            duration = 5.0
        
        self.img_to_vid_btn.configure(state="disabled", text="Processing...")
        
        # Start processing in thread
        def process():
            try:
                self.log("Starting Images to Videos conversion...")
                created = create_images_to_videos(
                    input_folder, 
                    output_folder, 
                    duration=duration,
                    logger=self.log
                )
                
                if created:
                    self.log(f"Completed! Created {len(created)} videos")
                    self.after(0, lambda: messagebox.showinfo("Success", f"Created {len(created)} videos!"))
                else:
                    self.log("No videos were created")
                    self.after(0, lambda: messagebox.showwarning("Warning", "No images found or processed."))
            except Exception as e:
                self.log(f"Error: {e}")
                self.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {e}"))
            finally:
                self.after(0, lambda: self.img_to_vid_btn.configure(state="normal", text="Images to Videos"))
        
        thread = threading.Thread(target=process)
        thread.start()

    def open_news_anchor_generator(self):
        """Open the News Anchor Generator dialog."""
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("Error", "Please enter an API Key first.")
            return
        
        NewsAnchorGeneratorWindow(self, api_key)


class NewsAnchorGeneratorWindow(ctk.CTkToplevel):
    """Window for generating AI News Anchor videos using Veo 3.0 Fast with auto-extend support."""
    
    # Approximate characters per video segment (~10 seconds of speech)
    CHARS_PER_SEGMENT = 180  # Characters per segment
    
    # Veo pricing (approximate)
    VEO_COST_PER_VIDEO = 0.35  # USD per 8-second video
    
    def __init__(self, parent, api_key):
        super().__init__(parent)
        self.parent = parent
        self.api_key = api_key
        self.title("📺 AI News Anchor Generator")
        self.geometry("1050x950")
        self.minsize(1000, 900)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.is_generating = False
        self.generated_videos = []
        self.last_video_uri = None
        self.last_output_folder = None
        self.last_aspect_ratio = None
        self.script_segments = []
        self.current_segment_index = 0
        self.overlay_media_list = []  # List of overlay images/videos
        self.total_cost = 0.0
        self.last_api_call = 0  # Timestamp of last API call
        self.API_DELAY_SECONDS = 35  # Wait 35 seconds between calls (2 per minute limit)
        
        self.create_ui()
    
    def split_script(self, script):
        """Split script into segments for video generation."""
        script = script.strip()
        if not script:
            return []
        
        # Split by sentences (periods, question marks, exclamation marks)
        import re
        sentences = re.split(r'(?<=[.!?])\s+', script)
        
        segments = []
        current_segment = ""
        
        for sentence in sentences:
            if len(current_segment) + len(sentence) <= self.CHARS_PER_SEGMENT:
                current_segment += sentence + " "
            else:
                if current_segment.strip():
                    segments.append(current_segment.strip())
                current_segment = sentence + " "
        
        # Add remaining
        if current_segment.strip():
            segments.append(current_segment.strip())
        
        # If no segments, put whole script as one
        if not segments:
            segments = [script]
        
        return segments
    
    def update_segment_info(self, event=None):
        """Update the segment count display when script changes."""
        script = self.script_textbox.get("1.0", "end-1c").strip()
        if script:
            segments = self.split_script(script)
            estimated_cost = len(segments) * self.VEO_COST_PER_VIDEO
            self.segment_count_label.configure(
                text=f"📊 แบ่งเป็น {len(segments)} ส่วน (~{len(segments) * 8} วินาที) | 💰 ประมาณ ${estimated_cost:.2f} USD"
            )
            self.script_segments = segments
        else:
            self.segment_count_label.configure(text="📊 กรุณากรอก Script")
            self.script_segments = []
    
    def create_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, pady=(10, 5), sticky="ew")
        
        header = ctk.CTkLabel(header_frame, text="📺 AI News Anchor Generator", font=ctk.CTkFont(size=20, weight="bold"))
        header.pack()
        
        subtitle = ctk.CTkLabel(header_frame, text="Create AI News Anchor Videos with Veo 3.0 Fast + Auto-Extend", font=ctk.CTkFont(size=10))
        subtitle.pack()
        
        # Main container
        self.grid_columnconfigure(0, weight=0, minsize=320)  # Left - Settings (fixed width)
        self.grid_columnconfigure(1, weight=1)  # Right - Script + Log (expandable)
        self.grid_rowconfigure(1, weight=1)
        
        # ===================== LEFT COLUMN - Settings (Scrollable) =====================
        left_container = ctk.CTkFrame(self, width=320)
        left_container.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="nsew")
        left_container.grid_propagate(False)
        
        # Scrollable frame for settings
        left_scroll = ctk.CTkScrollableFrame(left_container, width=300)
        left_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(left_scroll, text="⚙️ Settings", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(5, 10))
        
        # API Key Management
        api_box = ctk.CTkFrame(left_scroll)
        api_box.pack(fill="x", pady=5)
        ctk.CTkLabel(api_box, text="🔑 API Keys", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=3)
        
        # Saved keys dropdown
        api_select_row = ctk.CTkFrame(api_box, fg_color="transparent")
        api_select_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(api_select_row, text="Select:", width=45).pack(side="left")
        self.api_keys_dict = self.load_api_keys()  # {name: key}
        self.selected_api_name = ctk.StringVar(value="-- Select Key --")
        key_names = list(self.api_keys_dict.keys()) if self.api_keys_dict else ["-- No saved keys --"]
        self.api_dropdown = ctk.CTkOptionMenu(api_select_row, variable=self.selected_api_name, values=key_names, width=130, command=self.on_api_key_selected)
        self.api_dropdown.pack(side="left", padx=3)
        
        # API Key input
        api_input_row = ctk.CTkFrame(api_box, fg_color="transparent")
        api_input_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(api_input_row, text="Key:", width=45).pack(side="left")
        self.veo_api_key_var = ctk.StringVar(value="")
        self.veo_api_entry = ctk.CTkEntry(api_input_row, textvariable=self.veo_api_key_var, width=160, show="*", placeholder_text="API Key")
        self.veo_api_entry.pack(side="left", padx=3)
        
        # Key name for saving
        api_name_row = ctk.CTkFrame(api_box, fg_color="transparent")
        api_name_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(api_name_row, text="Name:", width=45).pack(side="left")
        self.api_name_var = ctk.StringVar(value="")
        ctk.CTkEntry(api_name_row, textvariable=self.api_name_var, width=100, placeholder_text="Key name").pack(side="left", padx=3)
        ctk.CTkButton(api_name_row, text="💾 Save", command=self.save_api_key, width=50, fg_color="green").pack(side="left", padx=2)
        
        # Buttons row
        api_btn_row = ctk.CTkFrame(api_box, fg_color="transparent")
        api_btn_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkButton(api_btn_row, text="✓ Check API", command=self.check_api_key, width=80, fg_color="purple").pack(side="left", padx=3)
        ctk.CTkButton(api_btn_row, text="🗑️ Delete", command=self.delete_api_key, width=60, fg_color="gray").pack(side="left", padx=3)
        
        # Language (Default: English)
        lang_frame = ctk.CTkFrame(left_scroll, fg_color="transparent")
        lang_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(lang_frame, text="Language:", width=90).pack(side="left")
        self.language_var = ctk.StringVar(value="English")
        self.language_dropdown = ctk.CTkOptionMenu(lang_frame, variable=self.language_var, values=list(SUPPORTED_LANGUAGES.keys()), width=140)
        self.language_dropdown.pack(side="left", padx=5)
        
        # Aspect Ratio (Default: 9:16)
        aspect_frame = ctk.CTkFrame(left_scroll, fg_color="transparent")
        aspect_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(aspect_frame, text="Aspect Ratio:", width=90).pack(side="left")
        self.aspect_ratio_var = ctk.StringVar(value="9:16")
        ctk.CTkRadioButton(aspect_frame, text="16:9", variable=self.aspect_ratio_var, value="16:9").pack(side="left", padx=3)
        ctk.CTkRadioButton(aspect_frame, text="9:16", variable=self.aspect_ratio_var, value="9:16").pack(side="left", padx=3)
        
        # Reference Image
        ref_frame = ctk.CTkFrame(left_scroll, fg_color="transparent")
        ref_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(ref_frame, text="Ref. Image:", width=90).pack(side="left")
        self.reference_image_path = None
        self.ref_image_label = ctk.CTkLabel(ref_frame, text="Not selected", font=ctk.CTkFont(size=9), width=100)
        self.ref_image_label.pack(side="left")
        ctk.CTkButton(ref_frame, text="📷", command=self.select_reference_image, width=30).pack(side="left", padx=2)
        ctk.CTkButton(ref_frame, text="❌", command=self.clear_reference_image, width=30, fg_color="gray").pack(side="left")
        
        # Output Folder
        output_frame = ctk.CTkFrame(left_scroll, fg_color="transparent")
        output_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(output_frame, text="Output:", width=90).pack(side="left")
        self.output_path_var = ctk.StringVar(value="")
        ctk.CTkEntry(output_frame, textvariable=self.output_path_var, width=140).pack(side="left", padx=3)
        ctk.CTkButton(output_frame, text="📁", command=self.browse_output, width=30).pack(side="left")
        
        # Extension Mode
        extend_box = ctk.CTkFrame(left_scroll)
        extend_box.pack(fill="x", pady=8)
        ctk.CTkLabel(extend_box, text="🔄 Extension Mode", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=3)
        self.auto_extend_var = ctk.BooleanVar(value=True)
        ctk.CTkRadioButton(extend_box, text="Auto-Extend (split script)", variable=self.auto_extend_var, value=True).pack(anchor="w", padx=10)
        ctk.CTkRadioButton(extend_box, text="Manual (extend manually)", variable=self.auto_extend_var, value=False).pack(anchor="w", padx=10)
        
        # Subtitle Options (Default: Word mode)
        sub_box = ctk.CTkFrame(left_scroll)
        sub_box.pack(fill="x", pady=8)
        ctk.CTkLabel(sub_box, text="📝 Subtitles", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=3)
        self.subtitle_enabled_var = ctk.BooleanVar(value=True)  # Default: enabled
        ctk.CTkCheckBox(sub_box, text="Generate Subtitles", variable=self.subtitle_enabled_var).pack(anchor="w", padx=10)
        
        sub_mode_row = ctk.CTkFrame(sub_box, fg_color="transparent")
        sub_mode_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(sub_mode_row, text="Mode:", width=45).pack(side="left")
        self.subtitle_mode_var = ctk.StringVar(value="word")  # Default: word
        ctk.CTkRadioButton(sub_mode_row, text="Sentence", variable=self.subtitle_mode_var, value="sentence").pack(side="left", padx=3)
        ctk.CTkRadioButton(sub_mode_row, text="Word", variable=self.subtitle_mode_var, value="word").pack(side="left", padx=3)
        
        # Subtitle Position
        sub_pos_row = ctk.CTkFrame(sub_box, fg_color="transparent")
        sub_pos_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(sub_pos_row, text="Position:", width=45).pack(side="left")
        self.subtitle_margin_var = ctk.StringVar(value="222")
        ctk.CTkEntry(sub_pos_row, textvariable=self.subtitle_margin_var, width=40).pack(side="left", padx=3)
        ctk.CTkLabel(sub_pos_row, text="px").pack(side="left")
        
        # Subtitle Font Size
        sub_font_row = ctk.CTkFrame(sub_box, fg_color="transparent")
        sub_font_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(sub_font_row, text="Font:", width=45).pack(side="left")
        self.subtitle_fontsize_var = ctk.StringVar(value="25")
        ctk.CTkEntry(sub_font_row, textvariable=self.subtitle_fontsize_var, width=40).pack(side="left", padx=3)
        ctk.CTkLabel(sub_font_row, text="px").pack(side="left")
        
        # Subtitle Color
        sub_color_row = ctk.CTkFrame(sub_box, fg_color="transparent")
        sub_color_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(sub_color_row, text="Color:", width=45).pack(side="left")
        self.subtitle_color_var = ctk.StringVar(value="#ffec00")
        self.sub_color_btn = ctk.CTkButton(sub_color_row, text="● #ffec00", command=self.pick_subtitle_color, width=70, fg_color="#555555")
        self.sub_color_btn.pack(side="left", padx=3)
        ctk.CTkButton(sub_color_row, text="👁 Preview", command=self.preview_subtitle, width=65, fg_color="purple").pack(side="left", padx=3)
        
        # Overlay/Insert Media (Full screen with fade)
        overlay_box = ctk.CTkFrame(left_scroll)
        overlay_box.pack(fill="x", pady=8)
        ctk.CTkLabel(overlay_box, text="🎞️ Insert Media (Full Screen)", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=3)
        self.overlay_listbox = ctk.CTkTextbox(overlay_box, height=50, state="disabled")
        self.overlay_listbox.pack(fill="x", padx=10, pady=2)
        overlay_btns = ctk.CTkFrame(overlay_box, fg_color="transparent")
        overlay_btns.pack(pady=3)
        ctk.CTkButton(overlay_btns, text="➕ Add", command=self.add_overlay_media, width=55).pack(side="left", padx=3)
        ctk.CTkButton(overlay_btns, text="🗑️ Clear", command=self.clear_overlay_media, width=55, fg_color="gray").pack(side="left", padx=3)
        
        # ===================== RIGHT COLUMN - Script + Log =====================
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=2)  # Script area
        right_frame.grid_rowconfigure(3, weight=1)  # Log area
        
        # Script Section
        ctk.CTkLabel(right_frame, text="📝 Script", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, pady=(10, 5))
        
        self.script_textbox = ctk.CTkTextbox(right_frame)
        self.script_textbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.script_textbox.bind("<KeyRelease>", self.update_segment_info)
        
        # Segment Info + Cost
        self.segment_count_label = ctk.CTkLabel(right_frame, text="📊 Enter script to see segment info", font=ctk.CTkFont(size=10))
        self.segment_count_label.grid(row=2, column=0, pady=3)
        
        # Log Section
        log_header = ctk.CTkFrame(right_frame, fg_color="transparent")
        log_header.grid(row=3, column=0, sticky="ew", padx=10)
        ctk.CTkLabel(log_header, text="📋 Log", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.status_label = ctk.CTkLabel(log_header, text="Ready", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="right")
        
        self.log_textbox = ctk.CTkTextbox(right_frame, height=100)
        self.log_textbox.grid(row=4, column=0, padx=10, pady=(3, 5), sticky="nsew")
        self.log_textbox.configure(state="disabled")
        
        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(right_frame)
        self.progress_bar.grid(row=5, column=0, padx=10, pady=5, sticky="ew")
        self.progress_bar.set(0)
        
        self.segment_progress_label = ctk.CTkLabel(right_frame, text="", font=ctk.CTkFont(size=10))
        self.segment_progress_label.grid(row=6, column=0, pady=2)
        
        # ===================== BUTTONS (Bottom) =====================
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.generate_btn = ctk.CTkButton(btn_frame, text="🎬 Generate Video", command=self.start_generation, 
                                          fg_color="green", hover_color="darkgreen", width=150, height=38)
        self.generate_btn.pack(side="left", padx=8)
        
        self.extend_btn = ctk.CTkButton(btn_frame, text="➕ Extend (Manual)", command=self.start_extension, 
                                        fg_color="#FF9800", hover_color="#F57C00", width=130, height=38, state="disabled")
        self.extend_btn.pack(side="left", padx=8)
        
        self.cancel_btn = ctk.CTkButton(btn_frame, text="❌ Cancel", command=self.cancel_generation, 
                                        fg_color="gray", width=90, height=38)
        self.cancel_btn.pack(side="left", padx=8)
    
    def log(self, message):
        """Log a message to the textbox."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")
        self.update_idletasks()
    
    def browse_output(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_path_var.set(path)
    
    def select_reference_image(self):
        path = filedialog.askopenfilename(
            title="Select Reference Image",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.webp")]
        )
        if path:
            self.reference_image_path = path
            self.ref_image_label.configure(text=os.path.basename(path)[:20])
            self.log(f"Reference: {os.path.basename(path)}")
    
    def clear_reference_image(self):
        self.reference_image_path = None
        self.ref_image_label.configure(text="ไม่ได้เลือก")
    
    def add_overlay_media(self):
        """Add overlay image or video for insertion."""
        paths = filedialog.askopenfilenames(
            title="Select Images/Videos to Insert",
            filetypes=[("Media Files", "*.jpg *.jpeg *.png *.webp *.mp4 *.mov *.avi")]
        )
        if paths:
            for path in paths:
                self.overlay_media_list.append(path)
            self.update_overlay_display()
            self.log(f"Added {len(paths)} overlay media files")
    
    def clear_overlay_media(self):
        """Clear all overlay media."""
        self.overlay_media_list = []
        self.update_overlay_display()
    
    def update_overlay_display(self):
        """Update the overlay listbox display."""
        self.overlay_listbox.configure(state="normal")
        self.overlay_listbox.delete("1.0", "end")
        if self.overlay_media_list:
            for i, path in enumerate(self.overlay_media_list):
                self.overlay_listbox.insert("end", f"{i+1}. {os.path.basename(path)}\n")
        else:
            self.overlay_listbox.insert("end", "No media to insert")
        self.overlay_listbox.configure(state="disabled")
    
    def get_api_keys_file(self):
        """Get path to API keys storage file."""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "veo_api_keys.json")
    
    def load_api_keys(self):
        """Load saved API keys from file."""
        try:
            import json
            filepath = self.get_api_keys_file()
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def save_api_keys_to_file(self, keys_dict):
        """Save API keys to file."""
        import json
        filepath = self.get_api_keys_file()
        with open(filepath, 'w') as f:
            json.dump(keys_dict, f, indent=2)
    
    def save_api_key(self):
        """Save current API key with name."""
        name = self.api_name_var.get().strip()
        key = self.veo_api_key_var.get().strip()
        
        if not name:
            messagebox.showerror("Error", "กรุณากรอกชื่อ Key")
            return
        if not key:
            messagebox.showerror("Error", "กรุณากรอก API Key")
            return
        
        self.api_keys_dict[name] = key
        self.save_api_keys_to_file(self.api_keys_dict)
        self.refresh_api_dropdown()
        self.selected_api_name.set(name)
        self.log(f"✅ Saved API key: {name}")
        messagebox.showinfo("Success", f"Saved API key: {name}")
    
    def delete_api_key(self):
        """Delete selected API key."""
        name = self.selected_api_name.get()
        if name in self.api_keys_dict:
            if messagebox.askyesno("Confirm", f"Delete API key '{name}'?"):
                del self.api_keys_dict[name]
                self.save_api_keys_to_file(self.api_keys_dict)
                self.refresh_api_dropdown()
                self.veo_api_key_var.set("")
                self.log(f"🗑️ Deleted API key: {name}")
    
    def on_api_key_selected(self, name):
        """Handle API key selection from dropdown."""
        if name in self.api_keys_dict:
            self.veo_api_key_var.set(self.api_keys_dict[name])
            self.log(f"Selected API key: {name}")
    
    def refresh_api_dropdown(self):
        """Refresh API keys dropdown."""
        key_names = list(self.api_keys_dict.keys()) if self.api_keys_dict else ["-- No saved keys --"]
        self.api_dropdown.configure(values=key_names)
        if key_names and key_names[0] != "-- No saved keys --":
            self.selected_api_name.set(key_names[0])
        else:
            self.selected_api_name.set("-- Select Key --")
    
    def check_api_key(self):
        """Check if API key is valid."""
        api_key = self.veo_api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("Error", "กรุณากรอก API Key")
            return
        
        self.log("Checking API key...")
        
        def check_thread():
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    self.after(0, lambda: self.log("✅ API key is valid!"))
                    self.after(0, lambda: messagebox.showinfo("Success", "API key is valid!"))
                elif response.status_code == 401:
                    self.after(0, lambda: self.log("❌ Invalid API key"))
                    self.after(0, lambda: messagebox.showerror("Error", "Invalid API key"))
                else:
                    self.after(0, lambda c=response.status_code: self.log(f"⚠️ API check: status {c}"))
                    self.after(0, lambda c=response.status_code: messagebox.showwarning("Warning", f"Status: {c}"))
            except Exception as e:
                self.after(0, lambda err=str(e): self.log(f"Error: {err}"))
                self.after(0, lambda err=str(e): messagebox.showerror("Error", f"Connection error: {err}"))
        
        threading.Thread(target=check_thread).start()
    
    def pick_subtitle_color(self):
        """Open color picker for subtitle color."""
        color = colorchooser.askcolor(title="Choose Subtitle Color", initialcolor=self.subtitle_color_var.get())
        if color[1]:
            self.subtitle_color_var.set(color[1])
            # Update button text with color preview
            self.sub_color_btn.configure(text=f"● {color[1]}")
            self.log(f"Subtitle color: {color[1]}")
    
    def preview_subtitle(self):
        """Preview subtitle appearance using ffmpeg with actual position."""
        import subprocess
        import tempfile
        
        try:
            margin = int(self.subtitle_margin_var.get() or 200)
        except ValueError:
            margin = 200
        
        try:
            font_size = int(self.subtitle_fontsize_var.get() or 48)
        except ValueError:
            font_size = 48
            
        color = self.subtitle_color_var.get() or "#FFFFFF"
        hex_color = color.lstrip('#')
        
        # For 9:16 video (1080x1920)
        width = 1080
        height = 1920
        
        # Calculate Y position from bottom
        y_position = height - margin - font_size
        
        self.log(f"Preview: margin={margin}px, font={font_size}px")
        self.log(f"Text Y position: {y_position}px from top")
        self.log(f"Color: {color}")
        
        try:
            preview_path = tempfile.NamedTemporaryFile(suffix='.png', delete=False).name
            
            # Create preview with:
            # - Black background (simulating video)
            # - Sample subtitle at exact position
            # - Guide lines to show position
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'color=c=0x222222:s={width}x{height}:d=1',
                '-vf', 
                f"drawtext=text='Subtitle Position Preview':fontsize=32:fontcolor=gray:x=(w-text_w)/2:y=50,"
                f"drawtext=text='margin\\={margin}px from bottom':fontsize=24:fontcolor=gray:x=(w-text_w)/2:y=100,"
                f"drawbox=x=0:y={y_position-10}:w={width}:h=2:color=red@0.5:t=fill,"
                f"drawtext=text='Sample Subtitle Text':fontsize={font_size}:fontcolor={hex_color}:x=(w-text_w)/2:y={y_position}:borderw=2:bordercolor=black,"
                f"drawtext=text='↑ {margin}px ↓':fontsize=20:fontcolor=yellow:x=(w-text_w)/2:y={height-margin//2}",
                '-frames:v', '1',
                preview_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(preview_path):
                subprocess.run(['open', preview_path])
                self.log("✅ Preview opened")
            else:
                self.log(f"FFmpeg error: {result.stderr[:300]}")
        except Exception as e:
            self.log(f"Preview error: {e}")
    
    def update_status(self, text):
        self.status_label.configure(text=text)
        self.update_idletasks()
    
    def update_progress(self, value):
        self.progress_bar.set(value)
        self.update_idletasks()
    
    def cancel_generation(self):
        self.is_generating = False
        self.update_status("Cancelled")
        self.generate_btn.configure(state="normal", text="🎬 Generate Video")
        self.extend_btn.configure(state="normal" if self.last_video_uri else "disabled", text="➕ Extend (Manual)")
    
    def start_generation(self):
        """Start video generation (with auto-extend if enabled)."""
        script = self.script_textbox.get("1.0", "end-1c").strip()
        if not script:
            messagebox.showerror("Error", "กรุณากรอก Script")
            return
        
        output_folder = self.output_path_var.get().strip()
        if not output_folder:
            messagebox.showerror("Error", "กรุณาเลือก Output Folder")
            return
        
        # Get API key from local field first, fallback to parent
        api_key = self.veo_api_key_var.get().strip()
        if not api_key:
            # Try to get from parent app
            try:
                api_key = self.parent.api_key_entry.get().strip()
            except:
                pass
        
        if not api_key:
            messagebox.showerror("Error", "กรุณากรอก API Key")
            return
        
        self.api_key = api_key
        
        os.makedirs(output_folder, exist_ok=True)
        
        # Split script
        self.script_segments = self.split_script(script)
        self.current_segment_index = 0
        
        # Disable buttons
        self.generate_btn.configure(state="disabled", text="Generating...")
        self.extend_btn.configure(state="disabled")
        self.is_generating = True
        
        # Get settings
        language_name = self.language_var.get()
        language_code = SUPPORTED_LANGUAGES.get(language_name, "en")
        aspect_ratio = self.aspect_ratio_var.get()
        reference_image = self.reference_image_path
        auto_extend = self.auto_extend_var.get()
        
        self.last_output_folder = output_folder
        self.last_aspect_ratio = aspect_ratio
        
        # Start in thread
        threading.Thread(target=self._generate_with_auto_extend, 
                        args=(language_code, aspect_ratio, output_folder, reference_image, auto_extend)).start()
    
    def _generate_with_auto_extend(self, language_code, aspect_ratio, output_folder, reference_image, auto_extend):
        """Generate video with optional auto-extend."""
        try:
            total_segments = len(self.script_segments)
            self.after(0, lambda: self.log(f"Script แบ่งเป็น {total_segments} ส่วน"))
            self.after(0, lambda: self.segment_progress_label.configure(text=f"ส่วนที่ 1/{total_segments}"))
            
            # Generate first segment
            first_segment = self.script_segments[0]
            self.after(0, lambda: self.update_status(f"กำลังสร้างส่วนที่ 1/{total_segments}..."))
            self.after(0, lambda: self.log(f"[1/{total_segments}] {first_segment[:50]}..."))
            
            # Rate limiting: wait if needed
            elapsed = time.time() - self.last_api_call
            if elapsed < self.API_DELAY_SECONDS and self.last_api_call > 0:
                wait_time = int(self.API_DELAY_SECONDS - elapsed)
                self.after(0, lambda w=wait_time: self.log(f"⏳ Rate limit: waiting {w}s before API call..."))
                for i in range(wait_time, 0, -1):
                    if not self.is_generating:
                        return
                    self.after(0, lambda sec=i: self.update_status(f"⏳ Rate limit: {sec}s..."))
                    time.sleep(1)
            
            timestamp = int(time.time())
            output_path = os.path.join(output_folder, f"news_anchor_{language_code}_{timestamp}.mp4")
            
            self.last_api_call = time.time()  # Mark API call time
            result = generate_news_anchor_video(
                script=first_segment,
                aspect_ratio=aspect_ratio,
                language_code=language_code,
                api_key=self.api_key,
                output_path=output_path,
                logger=lambda msg: self.after(0, lambda m=msg: self.log(m)),
                reference_image=reference_image
            )
            
            if not self.is_generating or not result:
                self.after(0, lambda: self.update_status("Failed or cancelled"))
                return
            
            self.last_video_uri = result.get("video_uri")
            self.generated_videos.append(result.get("output_path"))
            progress = 1 / total_segments
            self.after(0, lambda: self.update_progress(progress))
            
            # Auto-extend remaining segments
            if auto_extend and total_segments > 1:
                from core.veo_generator import generate_news_anchor_prompt
                
                for i in range(1, total_segments):
                    if not self.is_generating:
                        return
                    
                    segment = self.script_segments[i]
                    self.after(0, lambda idx=i+1, t=total_segments: self.segment_progress_label.configure(text=f"ส่วนที่ {idx}/{t}"))
                    self.after(0, lambda idx=i+1, t=total_segments: self.update_status(f"กำลัง Extend ส่วนที่ {idx}/{t}..."))
                    self.after(0, lambda idx=i+1, t=total_segments, s=segment: self.log(f"[{idx}/{t}] {s[:50]}..."))
                    
                    prompt = generate_news_anchor_prompt(segment, language_code)
                    ext_timestamp = int(time.time())
                    ext_output_path = os.path.join(output_folder, f"news_anchor_ext{i}_{language_code}_{ext_timestamp}.mp4")
                    
                    # Rate limiting: wait if needed
                    elapsed = time.time() - self.last_api_call
                    if elapsed < self.API_DELAY_SECONDS:
                        wait_time = int(self.API_DELAY_SECONDS - elapsed)
                        self.after(0, lambda w=wait_time: self.log(f"⏳ Rate limit: waiting {w}s..."))
                        for sec in range(wait_time, 0, -1):
                            if not self.is_generating:
                                return
                            self.after(0, lambda s=sec: self.update_status(f"⏳ Rate limit: {s}s..."))
                            time.sleep(1)
                    
                    # Try extension with retry
                    ext_result = None
                    max_retries = 2
                    for attempt in range(max_retries):
                        self.after(0, lambda a=attempt+1: self.log(f"Extension attempt {a}/{max_retries}..."))
                        self.last_api_call = time.time()  # Mark API call time
                        ext_result = extend_video(
                            video_uri=self.last_video_uri,
                            prompt=prompt,
                            aspect_ratio=aspect_ratio,
                            api_key=self.api_key,
                            output_path=ext_output_path,
                            logger=lambda msg: self.after(0, lambda m=msg: self.log(m))
                        )
                        if ext_result:
                            break
                        if attempt < max_retries - 1:
                            self.after(0, lambda: self.log("⚠️ Retrying extension..."))
                            time.sleep(2)
                    
                    if not ext_result:
                        self.after(0, lambda idx=i+1: self.log(f"❌ Extension {idx} failed after {max_retries} attempts"))
                        self.after(0, lambda: self.log("⚠️ Continuing with available segments..."))
                        break
                    
                    self.last_video_uri = ext_result.get("video_uri")
                    self.generated_videos.append(ext_result.get("output_path"))
                    progress = (i + 1) / total_segments
                    self.after(0, lambda p=progress: self.update_progress(p))
                    self.after(0, lambda idx=i+1: self.log(f"✅ Segment {idx} completed"))
            # Post-processing on final video
            final_video = self.generated_videos[-1] if self.generated_videos else output_path
            
            # Calculate and display cost
            self.total_cost = len(self.generated_videos) * self.VEO_COST_PER_VIDEO
            self.after(0, lambda: self.log(f"💰 Total cost: ${self.total_cost:.2f} USD"))
            
            # Insert overlay media FIRST (so subtitles appear on top)
            if self.overlay_media_list:
                self.after(0, lambda: self.update_status("กำลังแทรก Media..."))
                current_video = final_video
                
                # Insert overlays starting at 5 seconds, spaced by overlay duration + 2s gap
                base_start_time = 5.0
                overlay_duration = 6.5
                gap_between = 2.0
                
                for i, overlay_path in enumerate(self.overlay_media_list):
                    start_time = base_start_time + (i * (overlay_duration + gap_between))
                    overlay_output = current_video.replace(".mp4", f"_overlay{i}.mp4")
                    
                    overlay_result = insert_overlay_with_fade(
                        video_path=current_video,
                        overlay_path=overlay_path,
                        output_path=overlay_output,
                        start_time=start_time,
                        duration=overlay_duration,
                        fade_duration=0.5,
                        logger=lambda msg: self.after(0, lambda m=msg: self.log(m))
                    )
                    if overlay_result:
                        current_video = overlay_result
                        self.after(0, lambda idx=i+1, st=start_time: self.log(f"✅ Overlay {idx} inserted at {st:.1f}s"))
                
                final_video = current_video
            
            # Apply subtitles LAST (so they appear on top of overlays)
            if self.subtitle_enabled_var.get():
                self.after(0, lambda: self.update_status("กำลังสร้าง Subtitle..."))
                subtitle_mode = self.subtitle_mode_var.get()
                subtitle_margin = int(self.subtitle_margin_var.get() or 200)
                subtitle_fontsize = int(self.subtitle_fontsize_var.get() or 48)
                subtitle_color = self.subtitle_color_var.get() or "#FFFFFF"
                full_script = " ".join(self.script_segments)
                
                subtitled_path = final_video.replace(".mp4", "_subtitled.mp4")
                sub_result = burn_subtitles_for_news(
                    video_path=final_video,
                    subtitle_text=full_script,
                    output_path=subtitled_path,
                    mode=subtitle_mode,
                    margin=subtitle_margin,
                    color=subtitle_color,
                    fontsize=subtitle_fontsize,
                    logger=lambda msg: self.after(0, lambda m=msg: self.log(m))
                )
                if sub_result:
                    final_video = sub_result
                    self.after(0, lambda: self.log("✅ Subtitles added"))
            
            # Rename final video with FINAL prefix for easy identification
            final_dir = os.path.dirname(final_video)
            final_name = f"FINAL_{timestamp}_{language_code}.mp4"
            final_output = os.path.join(final_dir, final_name)
            
            try:
                import shutil
                shutil.copy2(final_video, final_output)
                self.after(0, lambda: self.log(f"📁 Final video: {final_name}"))
                final_video = final_output
            except Exception as e:
                self.after(0, lambda err=str(e): self.log(f"Note: Could not rename final: {err}"))
            
            # Done
            self.after(0, lambda: self.update_status("✅ Generation Complete!"))
            self.after(0, lambda: self.update_progress(1.0))
            self.after(0, lambda: self.extend_btn.configure(state="normal"))
            
            cost_msg = f"💰 ค่าใช้จ่ายรวม: ${self.total_cost:.2f} USD"
            self.after(0, lambda: messagebox.showinfo("Success", 
                f"สร้างวิดีโอเสร็จแล้ว!\n\nสร้างทั้งหมด {len(self.generated_videos)} ส่วน\n{cost_msg}\n\nไฟล์สุดท้าย:\n{os.path.basename(final_video)}"))
            
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: self.update_status("Error occurred"))
            self.after(0, lambda msg=error_msg: self.log(f"Error: {msg}"))
            self.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"An error occurred: {msg}"))
        finally:
            self.is_generating = False
            self.after(0, lambda: self.generate_btn.configure(state="normal", text="🎬 Generate Video"))

    def start_extension(self):
        """Manual extension."""
        if not self.last_video_uri:
            messagebox.showerror("Error", "ไม่มีวิดีโอที่จะต่อ กรุณาสร้างวิดีโอก่อน")
            return
        
        extension_script = self.script_textbox.get("1.0", "end-1c").strip()
        if not extension_script:
            messagebox.showerror("Error", "กรุณากรอก Script สำหรับต่อเนื้อหา")
            return
        
        self.generate_btn.configure(state="disabled")
        self.extend_btn.configure(state="disabled", text="Extending...")
        self.is_generating = True
        
        language_name = self.language_var.get()
        language_code = SUPPORTED_LANGUAGES.get(language_name, "en")
        
        threading.Thread(target=self._extend_video_manual, args=(extension_script, language_code)).start()
    
    def _extend_video_manual(self, script, language_code):
        """Manual extend in background."""
        try:
            self.after(0, lambda: self.update_status("Extending video..."))
            self.after(0, lambda: self.update_progress(0.2))
            
            from core.veo_generator import generate_news_anchor_prompt
            prompt = generate_news_anchor_prompt(script, language_code)
            
            timestamp = int(time.time())
            output_path = os.path.join(self.last_output_folder, f"news_anchor_ext_{language_code}_{timestamp}.mp4")
            
            result = extend_video(
                video_uri=self.last_video_uri,
                prompt=prompt,
                aspect_ratio=self.last_aspect_ratio,
                api_key=self.api_key,
                output_path=output_path,
                logger=lambda msg: self.after(0, lambda m=msg: self.log(m))
            )
            
            if result:
                self.last_video_uri = result.get("video_uri")
                self.generated_videos.append(result.get("output_path"))
                self.after(0, lambda: self.update_status("✅ Extended!"))
                self.after(0, lambda: self.update_progress(1.0))
                self.after(0, lambda: messagebox.showinfo("Success", f"Extended to: {os.path.basename(output_path)}"))
            else:
                self.after(0, lambda: self.update_status("Extension failed"))
                self.after(0, lambda: messagebox.showerror("Error", "Extension failed"))
            
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda msg=error_msg: self.log(f"Error: {msg}"))
        finally:
            self.is_generating = False
            self.after(0, lambda: self.generate_btn.configure(state="normal", text="🎬 Generate Video"))
            self.after(0, lambda: self.extend_btn.configure(state="normal", text="➕ Extend (Manual)"))

class CoverGeneratorWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Cover Image Generator")
        self.geometry("1000x800")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Settings Panel (Left)
        self.settings_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.settings_frame.grid(row=0, column=0, sticky="nsew")
        
        # Preview Panel (Right)
        self.preview_frame = ctk.CTkFrame(self, corner_radius=0)
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        
        self.presets = load_cover_presets()
        
        self.create_settings_ui()
        self.create_preview_ui()
        
        # State
        self.current_frame_path = "temp_cover_frame.jpg"
        self.preview_image = None
        self.text_pos = (0.5, 0.5) # Normalized coordinates (0-1)
        
        # Initial Frame
        self.extract_random_frame()

    def create_settings_ui(self):
        # Presets
        ctk.CTkLabel(self.settings_frame, text="Presets", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), padx=10)
        preset_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        preset_frame.pack(pady=5, padx=10, fill="x")
        
        self.preset_var = ctk.StringVar(value="Select Preset")
        self.preset_dropdown = ctk.CTkOptionMenu(preset_frame, variable=self.preset_var, values=["Select Preset"] + list(self.presets.keys()), command=self.load_preset)
        self.preset_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.save_preset_btn = ctk.CTkButton(preset_frame, text="💾", width=30, command=self.save_preset_dialog)
        self.save_preset_btn.pack(side="left", padx=2)
        
        self.del_preset_btn = ctk.CTkButton(preset_frame, text="🗑️", width=30, fg_color="red", command=self.delete_preset)
        self.del_preset_btn.pack(side="left", padx=2)

        # Topic Input
        ctk.CTkLabel(self.settings_frame, text="Main Topic", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), padx=10)
        self.topic_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Enter topic to translate...")
        self.topic_entry.pack(pady=5, padx=10, fill="x")
        
        # Language Selection REMOVED - Controlled by Main App
        # ctk.CTkLabel(self.settings_frame, text="Target Languages", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5), padx=10)
        # self.lang_vars = {}
        # ... (removed scrollable frame)
            
        # Styling
            
        # Styling
        ctk.CTkLabel(self.settings_frame, text="Styling", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5), padx=10)
        
        # Font Size
        self.font_size_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Font Size (e.g. 80)")
        self.font_size_entry.insert(0, "80")
        self.font_size_entry.pack(pady=5, padx=10, fill="x")
        
        # Colors
        btn_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        btn_frame.pack(pady=5, padx=10, fill="x")
        
        self.text_color = "#FFFFFF"
        self.text_color_btn = ctk.CTkButton(btn_frame, text="Text Color", command=self.pick_text_color, fg_color=self.text_color)
        self.text_color_btn.pack(side="left", expand=True, padx=2)
        
        self.border_color = "#000000"
        self.border_color_btn = ctk.CTkButton(btn_frame, text="Border Color", command=self.pick_border_color, fg_color=self.border_color)
        self.border_color_btn.pack(side="left", expand=True, padx=2)
        
        # Border Width
        self.border_width_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Border Width")
        self.border_width_entry.insert(0, "4")
        self.border_width_entry.pack(pady=5, padx=10, fill="x")
        
        # Actions
        ctk.CTkLabel(self.settings_frame, text="Actions", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5), padx=10)
        
        ctk.CTkButton(self.settings_frame, text="Random Frame", command=self.extract_random_frame, fg_color="orange").pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(self.settings_frame, text="Update Preview", command=self.update_preview).pack(pady=5, padx=10, fill="x")
        
        self.generate_btn = ctk.CTkButton(self.settings_frame, text="Save Settings & Close", command=self.save_and_close, fg_color="green")
        self.generate_btn.pack(pady=20, padx=10, fill="x")

    def save_and_close(self):
        # Save settings to parent
        try:
            font_size = int(self.font_size_entry.get())
        except:
            font_size = 80
            
        try:
            border_width = int(self.border_width_entry.get())
        except:
            border_width = 4

        # Save the current frame to a persistent temp location
        persistent_frame_path = "cover_base_frame.jpg"
        if os.path.exists(self.current_frame_path):
            shutil.copy(self.current_frame_path, persistent_frame_path)

        self.parent.cover_settings = {
            "topic": self.topic_entry.get(),
            "image_path": persistent_frame_path,
            "style": {
                "font_size": font_size,
                "color": self.text_color,
                "border_color": self.border_color,
                "border_width": border_width,
                "position": self.text_pos,
                "anchor": "mm" # Default anchor
            }
        }
        messagebox.showinfo("Success", "Cover settings saved! Covers will be generated during export.")
        self.destroy()

    def generate_all(self):
        # Deprecated
        pass

    def create_preview_ui(self):
        self.canvas = tk.Canvas(self.preview_frame, bg="black")
        self.canvas.pack(fill="both", expand=True)
        
        # Bind resize
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        
        # Dragging
        self.canvas.bind("<Button-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag)

    def pick_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color", color=self.text_color)
        if color[1]:
            self.text_color = color[1]
            self.text_color_btn.configure(fg_color=self.text_color)
            self.update_preview()

    def pick_border_color(self):
        color = colorchooser.askcolor(title="Choose Border Color", color=self.border_color)
        if color[1]:
            self.border_color = color[1]
            self.border_color_btn.configure(fg_color=self.border_color)
            self.update_preview()

    def extract_random_frame(self):
        if not self.parent.source_video_path:
            return
            
        ratio = random.random()
        extract_frame(self.parent.source_video_path, self.current_frame_path, time_ratio=ratio)
        
        # Load image
        try:
            self.original_pil = Image.open(self.current_frame_path)
            self.update_preview()
        except Exception as e:
            print(f"Error loading frame: {e}")

    def on_canvas_resize(self, event):
        self.update_preview()

    def update_preview(self):
        if not hasattr(self, 'original_pil'):
            return
            
        # Resize image to fit canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
            
        img_w, img_h = self.original_pil.size
        scale = min(canvas_width/img_w, canvas_height/img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        
        resized = self.original_pil.resize((new_w, new_h))
        self.tk_image = ImageTk.PhotoImage(resized)
        
        self.canvas.delete("all")
        # Center image
        img_x = (canvas_width - new_w) // 2
        img_y = (canvas_height - new_h) // 2
        self.canvas.create_image(img_x, img_y, anchor="nw", image=self.tk_image)
        
        # Draw Text Preview
        text = self.topic_entry.get() or "Preview Text"
        
        try:
            font_size = int(self.font_size_entry.get())
        except:
            font_size = 80
            
        scaled_font_size = int(font_size * scale)
        
        # Calculate position
        # text_pos is normalized (0-1) relative to IMAGE
        # We need to map it to canvas coordinates
        # Image starts at img_x, img_y
        
        final_x = img_x + (self.text_pos[0] * new_w)
        final_y = img_y + (self.text_pos[1] * new_h)
        
        # Draw text on canvas (approximation)
        # Tkinter canvas text doesn't support stroke well, so we simulate or just show simple text
        # For better preview, we could use PIL to draw on a temp image, but that might be slow.
        # Let's just use canvas text for speed.
        
        font = ("Arial", scaled_font_size, "bold")
        
        # Calculate max width for wrapping (image width - margin)
        # We use a margin of 40px in backend (full scale).
        # Scaled margin:
        scaled_margin = 40 * scale
        max_width = new_w - scaled_margin
        
        # Shadow/Border simulation
        border_w = 2 # Simplified for preview
        self.canvas.create_text(final_x+border_w, final_y+border_w, text=text, font=font, fill=self.border_color, anchor="c", width=max_width, justify="left")
        self.canvas.create_text(final_x-border_w, final_y-border_w, text=text, font=font, fill=self.border_color, anchor="c", width=max_width, justify="left")
        self.canvas.create_text(final_x, final_y, text=text, font=font, fill=self.text_color, anchor="c", width=max_width, justify="left")
        
        # Store scale and offset for dragging
        self.img_scale = scale
        self.img_offset = (img_x, img_y)
        self.img_dims = (new_w, new_h)

    def on_drag_start(self, event):
        # Store start position for shift constraint
        self.drag_start_pos = self.text_pos

    def on_drag(self, event):
        if not hasattr(self, 'img_offset'):
            return
            
        # Convert canvas x,y to normalized image coordinates
        img_x, img_y = self.img_offset
        new_w, new_h = self.img_dims
        
        # Relative to image top-left
        rel_x = event.x - img_x
        rel_y = event.y - img_y
        
        # Normalize
        norm_x = rel_x / new_w
        norm_y = rel_y / new_h
        
        # Shift Constraint
        if event.state & 0x1: # Shift key mask (usually bit 0 or check specific platform)
            # On some systems Shift is bit 0 (1), others bit 2 (4).
            # Tkinter: Shift is 1.
            
            # Calculate delta from start
            start_x, start_y = self.drag_start_pos
            dx = abs(norm_x - start_x)
            dy = abs(norm_y - start_y)
            
            if dx > dy:
                # Lock Y
                norm_y = start_y
            else:
                # Lock X
                norm_x = start_x
        
        # Clamp
        norm_x = max(0, min(1, norm_x))
        norm_y = max(0, min(1, norm_y))
        
        self.text_pos = (norm_x, norm_y)
        self.update_preview()

    def save_preset_dialog(self):
        dialog = ctk.CTkInputDialog(text="Enter Preset Name:", title="Save Preset")
        name = dialog.get_input()
        if name:
            self.save_preset(name)

    def save_preset(self, name):
        # Gather current settings
        settings = {
            "font_size": self.font_size_entry.get(),
            "text_color": self.text_color,
            "border_color": self.border_color,
            "border_width": self.border_width_entry.get(),
            "text_pos": self.text_pos
        }
        self.presets[name] = settings
        save_cover_presets(self.presets)
        self.update_preset_dropdown()
        messagebox.showinfo("Success", f"Preset '{name}' saved!")

    def load_preset(self, name):
        if name in self.presets:
            data = self.presets[name]
            
            # Apply settings
            if "font_size" in data:
                self.font_size_entry.delete(0, "end")
                self.font_size_entry.insert(0, data["font_size"])
            
            if "text_color" in data:
                self.text_color = data["text_color"]
                self.text_color_btn.configure(fg_color=self.text_color)
                
            if "border_color" in data:
                self.border_color = data["border_color"]
                self.border_color_btn.configure(fg_color=self.border_color)
                
            if "border_width" in data:
                self.border_width_entry.delete(0, "end")
                self.border_width_entry.insert(0, data["border_width"])
                
            if "text_pos" in data:
                self.text_pos = tuple(data["text_pos"])
                
            self.update_preview()

    def delete_preset(self):
        name = self.preset_var.get()
        if name in self.presets:
            if messagebox.askyesno("Confirm", f"Delete preset '{name}'?"):
                del self.presets[name]
                save_cover_presets(self.presets)
                self.update_preset_dropdown()
                self.preset_var.set("Select Preset")

    def update_preset_dropdown(self):
        self.preset_dropdown.configure(values=["Select Preset"] + list(self.presets.keys()))

    def generate_all(self):
        topic = self.topic_entry.get().strip()
        if not topic:
            messagebox.showerror("Error", "Please enter a topic.")
            return
            
        selected_langs = [code for code, var in self.lang_vars.items() if var.get()]
        if not selected_langs:
            messagebox.showerror("Error", "Please select at least one language.")
            return
            
        api_key = self.parent.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("Error", "API Key is required for translation.")
            return
            
        export_dir = filedialog.askdirectory(title="Select Export Folder for Covers")
        if not export_dir:
            return
            
        self.generate_btn.configure(state="disabled", text="Generating...")
        
        threading.Thread(target=self._run_generation, args=(topic, selected_langs, api_key, export_dir)).start()

    def _run_generation(self, topic, languages, api_key, export_dir):
        try:
            # 1. Translate
            translations = {}
            # Add original language too if needed, or just use topic
            # Let's assume user wants translated versions.
            
            for lang_code in languages:
                # Find lang name
                lang_name = next((k for k, v in SUPPORTED_LANGUAGES.items() if v == lang_code), lang_code)
                
                print(f"Translating to {lang_name}...")
                translated = translate_text(topic, lang_code, api_key)
                if translated:
                    translations[lang_name] = translated
                else:
                    print(f"Failed to translate to {lang_name}")
            
            # 2. Generate Images
            # Prepare style
            try:
                font_size = int(self.font_size_entry.get())
            except:
                font_size = 80
                
            try:
                border_width = int(self.border_width_entry.get())
            except:
                border_width = 4
            
            # Convert normalized pos to pixels for the FULL SIZE image
            img_w, img_h = self.original_pil.size
            pos_x = int(self.text_pos[0] * img_w)
            pos_y = int(self.text_pos[1] * img_h)
            
            style = {
                "font_size": font_size,
                "color": self.text_color,
                "border_color": self.border_color,
                "border_width": border_width,
                "position": (pos_x, pos_y),
                "anchor": "mm" # Middle-Middle
            }
            
            for lang, text in translations.items():
                out_name = f"cover_{lang}_{topic[:10]}.jpg".replace(" ", "_")
                out_path = os.path.join(export_dir, out_name)
                
                draw_text_on_image(self.current_frame_path, text, out_path, style)
                
            self.parent.after(0, lambda: messagebox.showinfo("Success", f"Generated {len(translations)} covers!"))
            
        except Exception as e:
            print(f"Error: {e}")
            self.parent.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))
        finally:
            self.parent.after(0, lambda: self.generate_btn.configure(state="normal", text="Generate All Covers"))

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = VideoEditorApp()
    app.mainloop()
