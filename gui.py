import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
import os
import threading
import shutil
from PIL import Image, ImageTk
from core.tts import generate_audio, verify_api_key, GEMINI_VOICES
from core.subtitles import generate_subtitles, save_srt
from core.video import merge_audio_video, burn_subtitles, extract_frame, burn_subtitle_image
from core.video import merge_audio_video, burn_subtitles, extract_frame, burn_subtitle_image
from core.utils import generate_id, create_manifest, load_config, save_config, load_cover_presets, save_cover_presets
from core.translation import translate_text
from core.image_gen import draw_text_on_image
import random

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
        self.languages_data = {} # {lang_code: {text_widget, title_entry}}
        self.cover_settings = None # Stores settings from Cover Generator
        
        # Load Settings
        self.settings = load_config()
        self.subtitle_margin_v = self.settings.get("margin_v", 20)

        self.create_sidebar()
        self.create_main_area()
        
        # Bind close event to save settings
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.save_current_settings()
        self.destroy()

    def save_current_settings(self):
        data = {
            "api_key": self.api_key_entry.get().strip(),
            "font_name": self.font_name_entry.get(),
            "font_size": self.font_size_entry.get(),
            "font_color": self.selected_color,
            "subtitle_mode": self.sub_mode_var.get(),
            "margin_v": self.subtitle_margin_v,
            "voice": self.voice_var.get(),
            "audio_mode": self.audio_mode_var.get(),
            "music_path": self.music_path
        }
        save_config(data)

    def create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(10, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Paji Editor", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Video Selection
        self.select_video_btn = ctk.CTkButton(self.sidebar_frame, text="Select Source Video", command=self.select_video)
        self.select_video_btn.grid(row=1, column=0, padx=20, pady=10)
        
        self.video_label = ctk.CTkLabel(self.sidebar_frame, text="No video selected", wraplength=200)
        self.video_label.grid(row=2, column=0, padx=20, pady=(0, 20))

        # TTS Settings
        self.tts_label = ctk.CTkLabel(self.sidebar_frame, text="Gemini TTS Settings", font=ctk.CTkFont(weight="bold"))
        self.tts_label.grid(row=3, column=0, padx=20, pady=(10, 5))

        # API Key Input
        self.api_key_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Gemini API Key", show="*")
        self.api_key_entry.grid(row=4, column=0, padx=20, pady=5)
        if "api_key" in self.settings:
            self.api_key_entry.insert(0, self.settings["api_key"])

        # Voice Selection
        self.voice_var = ctk.StringVar(value=self.settings.get("voice", GEMINI_VOICES[0]))
        self.voice_dropdown = ctk.CTkOptionMenu(self.sidebar_frame, variable=self.voice_var, values=GEMINI_VOICES)
        self.voice_dropdown.grid(row=5, column=0, padx=20, pady=5)

        # Check API Button
        self.check_api_btn = ctk.CTkButton(self.sidebar_frame, text="Check API Status", command=self.check_api, width=100, fg_color="gray")
        self.check_api_btn.grid(row=6, column=0, padx=20, pady=5)

        # Audio/Video Mode
        self.audio_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Audio/Video Mode", font=ctk.CTkFont(weight="bold"))
        self.audio_mode_label.grid(row=7, column=0, padx=20, pady=(10, 5))

        self.audio_mode_var = ctk.StringVar(value=self.settings.get("audio_mode", "trim"))

        self.trim_radio = ctk.CTkRadioButton(self.sidebar_frame, text="Trim Video to Audio", variable=self.audio_mode_var, value="trim", command=self.toggle_music_options)
        self.trim_radio.grid(row=8, column=0, padx=20, pady=2, sticky="w")

        self.music_radio = ctk.CTkRadioButton(self.sidebar_frame, text="Add Background Music", variable=self.audio_mode_var, value="bg_music", command=self.toggle_music_options)
        self.music_radio.grid(row=9, column=0, padx=20, pady=2, sticky="w")

        # Music Selection
        self.music_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.music_frame.grid(row=10, column=0, padx=20, pady=5)

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
        self.settings_label.grid(row=11, column=0, padx=20, pady=(10, 5))

        self.font_name_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Font Name (e.g. Arial)")
        self.font_name_entry.insert(0, self.settings.get("font_name", "Arial"))
        self.font_name_entry.grid(row=12, column=0, padx=20, pady=5)

        self.font_size_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="Font Size")
        self.font_size_entry.insert(0, self.settings.get("font_size", "75"))
        self.font_size_entry.grid(row=13, column=0, padx=20, pady=5)

        self.color_btn = ctk.CTkButton(self.sidebar_frame, text="Pick Color", command=self.pick_color)
        self.color_btn.grid(row=14, column=0, padx=20, pady=5)
        self.selected_color = self.settings.get("font_color", "#FFFFFF")
        self.color_btn.configure(fg_color=self.selected_color, text_color="black" if self.selected_color.lower() > "#aaaaaa" else "white")
        
        self.sub_mode_var = ctk.StringVar(value=self.settings.get("subtitle_mode", "sentence"))
        self.sub_mode_switch = ctk.CTkSwitch(self.sidebar_frame, text="Word Level Subtitles", variable=self.sub_mode_var, onvalue="word", offvalue="sentence")
        self.sub_mode_switch.grid(row=15, column=0, padx=20, pady=10)

        self.pos_btn = ctk.CTkButton(self.sidebar_frame, text="Adjust Position", command=self.open_position_editor, fg_color="gray")
        self.pos_btn.grid(row=16, column=0, padx=20, pady=5)

        # Process Button
        self.process_btn = ctk.CTkButton(self.sidebar_frame, text="Generate & Export", command=self.start_processing, fg_color="green", hover_color="darkgreen")
        self.process_btn.grid(row=17, column=0, padx=20, pady=20)

        # Cover Generator Button
        self.cover_btn = ctk.CTkButton(self.sidebar_frame, text="Cover Generator", command=self.open_cover_generator, fg_color="purple", hover_color="#4a0072")
        self.cover_btn.grid(row=18, column=0, padx=20, pady=10)

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

    def select_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.mkv *.mov *.avi")])
        if path:
            self.source_video_path = path
            self.video_label.configure(text=os.path.basename(path))

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
        if not self.source_video_path:
            messagebox.showerror("Error", "Please select a source video first.")
            return
            
        editor = ctk.CTkToplevel(self)
        editor.title("Subtitle Position Editor")
        editor.geometry("800x600")
        
        # Extract frame
        frame_path = "temp_frame.jpg"
        if not extract_frame(self.source_video_path, frame_path):
            messagebox.showerror("Error", "Failed to extract frame from video.")
            editor.destroy()
            return
            
        # Load image
        pil_image = Image.open(frame_path)
        # Resize to fit window roughly
        img_width, img_height = pil_image.size
        # Scale down if too big
        max_w, max_h = 780, 500
        scale = min(max_w/img_width, max_h/img_height)
        new_w, new_h = int(img_width * scale), int(img_height * scale)
        pil_image_resized = pil_image.resize((new_w, new_h))
        tk_image = ImageTk.PhotoImage(pil_image_resized)
        
        canvas = tk.Canvas(editor, width=new_w, height=new_h, bg="black")
        canvas.pack(pady=10)
        canvas.create_image(0, 0, anchor="nw", image=tk_image)
        
        # Draw subtitle line
        # Initial position based on current margin
        # Margin is from bottom. In canvas y coordinates: height - margin
        # We need to scale the margin too? Yes.
        scaled_margin = self.subtitle_margin_v * scale
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
        margin_label = canvas.create_text(10, initial_y - 10, text=f"Margin: {self.subtitle_margin_v}px", fill="red", anchor="w", font=("Arial", 10))
        
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
        if not self.source_video_path:
            messagebox.showerror("Error", "Please select a source video first.")
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
                
            if script:
                tasks.append({
                    "name": lang_name,
                    "code": data["code"],
                    "script": script,
                    "title": title
                })
        
        if not tasks:
            messagebox.showerror("Error", "Please enter script and title for at least one language.")
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
                
                # Create language folder - REMOVED (Flat structure requested)
                # lang_dir = os.path.join(export_dir, lang_name)
                # os.makedirs(lang_dir, exist_ok=True)
                
                # Use export_dir directly
                lang_dir = export_dir
                
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
                
                # 1. Generate Audio
                self.log(f"[{lang_name}] Generating audio...")
                audio_file = generate_audio(
                    script, 
                    lang_code, 
                    audio_path, 
                    voice=self.voice_var.get(),
                    api_key=api_key
                )
                if not audio_file:
                    self.log(f"[{lang_name}] Failed to generate audio")
                    continue
                
                # 2. Merge Audio and Video
                self.log(f"[{lang_name}] Merging video...")
                merged_file = merge_audio_video(
                    self.source_video_path, 
                    audio_path, 
                    video_merged_path,
                    mode=self.audio_mode_var.get(),
                    music_path=self.music_path
                )
                if not merged_file:
                    self.log(f"[{lang_name}] Failed to merge video")
                    continue

                # 3. Generate Subtitles
                self.log(f"[{lang_name}] Generating subtitles...")
                subs = generate_subtitles(audio_path, language=lang_code, mode=self.sub_mode_var.get())
                save_srt(subs, srt_path)
                
                # 4. Burn Subtitles
                self.log(f"[{lang_name}] Burning subtitles...")
                font_settings = {
                    "Fontname": self.font_name_entry.get(),
                    "Fontsize": self.font_size_entry.get(),
                    "PrimaryColour": self.selected_color
                }
                final_file = burn_subtitles(merged_file, srt_path, font_settings, final_video_path, margin_v=self.subtitle_margin_v, logger=self.log)
                
                # Cleanup intermediate merged file if desired
                if os.path.exists(merged_file):
                    os.remove(merged_file)
                
                if final_file:
                    self.log(f"[{lang_name}] Completed: {os.path.basename(final_file)}")
                    manifest_data.append({
                        "id": video_id,
                        "language": lang_name,
                        "title": title,
                        "file_path": final_file
                    })
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
