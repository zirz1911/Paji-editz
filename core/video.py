import ffmpeg
import os

def merge_audio_video(video_path, audio_path, output_path, mode="trim", music_path=None, music_volume=0.15):
    """
    Merges video and audio using ffmpeg.
    mode="trim": Cut video to match TTS audio length.
    mode="bg_music": Keep video length, mix TTS with looped background music.
    """
    try:
        input_video = ffmpeg.input(video_path)
        input_tts = ffmpeg.input(audio_path)
        
        if mode == "bg_music" and music_path and os.path.exists(music_path):
            # Background Music Mode
            # Loop music, lower volume, mix with TTS
            input_music = ffmpeg.input(music_path, stream_loop=-1)
            
            # Adjust volumes
            # Note: amix averages inputs by default, so we might lose some volume.
            # We can use weights or just accept it.
            # Let's just set volumes relative to each other.
            music_audio = input_music.audio.filter('volume', music_volume)
            tts_audio = input_tts.audio # Keep original volume
            
            # Mix
            # duration='first' (if tts is first? no), 'longest' (infinite due to loop)
            # We want the mix to be continuous.
            mixed_audio = ffmpeg.filter([tts_audio, music_audio], 'amix', inputs=2, duration='longest')
            
            # Output with -shortest (to cut to video length)
            (
                ffmpeg
                .output(input_video.video, mixed_audio, output_path, vcodec='copy', acodec='aac', strict='experimental', shortest=None)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        else:
            # Trim Mode (or fallback if no music)
            # Cut video to match TTS audio length (shortest=None adds -shortest flag)
            # If mode is bg_music but no music file, we still might want to keep video length?
            # But if we use -shortest with just TTS, it will cut to TTS length.
            # If user wanted "Bg Music" (Keep Video Length) but didn't provide music,
            # we probably should NOT use -shortest?
            # But then audio stops and video continues silently.
            # Let's assume if no music, we behave like trim or just output.
            
            if mode == "bg_music":
                # User wants to keep video length, but no music provided.
                # Don't use shortest.
                (
                    ffmpeg
                    .output(input_video.video, input_tts.audio, output_path, vcodec='copy', acodec='aac', strict='experimental')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            else:
                # Trim mode: Use shortest
                (
                    ffmpeg
                    .output(input_video.video, input_tts.audio, output_path, vcodec='copy', acodec='aac', strict='experimental', shortest=None)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
        return output_path
    except ffmpeg.Error as e:
        print(f"FFmpeg error: {e.stderr.decode('utf8')}")
        return None

def extract_frame(video_path, output_path, time_ratio=0.5):
    """
    Extracts a single frame from the video at the given time ratio (0.0 to 1.0).
    """
    try:
        probe = ffmpeg.probe(video_path)
        duration = float(probe['format']['duration'])
        time = duration * time_ratio
        
        (
            ffmpeg
            .input(video_path, ss=time)
            .output(output_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path
    except Exception as e:
        print(f"Error extracting frame: {e}")
        return None

def burn_subtitles(video_path, subtitle_path, font_settings, output_path, margin_v=None, logger=None):
    """
    Burns subtitles into video.
    font_settings: dict with keys like 'Fontname', 'Fontsize', 'PrimaryColour'
    margin_v: Vertical margin from bottom (default None, uses ffmpeg default)
    logger: function to log messages (e.g. self.log)
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)

    try:
        # 1. Probe Video Dimensions
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if video_stream:
                width = int(video_stream['width'])
                height = int(video_stream['height'])
                log(f"Video Dimensions: {width}x{height}")
                
                if margin_v is not None:
                    if margin_v > height / 2:
                        log(f"WARNING: MarginV ({margin_v}) is more than half the video height ({height}). Subtitles might be too high!")
                    if margin_v > height:
                        log(f"ERROR: MarginV ({margin_v}) is larger than video height ({height}). Subtitles will be off-screen!")
            else:
                log("Warning: Could not determine video dimensions.")
        except Exception as e:
            log(f"Warning: Failed to probe video: {e}")

        # 2. Validate SRT Content
        if not os.path.exists(subtitle_path) or os.path.getsize(subtitle_path) == 0:
            log(f"Error: Subtitle file missing or empty: {subtitle_path}")
            return None
            
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()
            log(f"Subtitle Content Preview (First 100 chars):\n{content[:100]}...")

        # Construct style string
        # Defaults: Alignment=2 (Bottom Center), BorderStyle=1 (Outline), Outline=1, Shadow=0
        style_parts = ["Alignment=2", "BorderStyle=1", "Outline=1", "Shadow=0"]
        
        if 'Fontname' in font_settings and font_settings['Fontname']:
            style_parts.append(f"Fontname={font_settings['Fontname']}")
        if 'Fontsize' in font_settings and font_settings['Fontsize']:
            style_parts.append(f"Fontsize={font_settings['Fontsize']}")
        if 'PrimaryColour' in font_settings:
            # Convert hex #RRGGBB to &HBBGGRR
            c = font_settings['PrimaryColour'].replace('#', '')
            if len(c) == 6:
                ass_color = f"&H00{c[4:6]}{c[2:4]}{c[0:2]}"
                style_parts.append(f"PrimaryColour={ass_color}")
        
        # Add black outline for contrast
        style_parts.append("OutlineColour=&H00000000")
        
        if margin_v is not None:
            style_parts.append(f"MarginV={margin_v}")
        
        style_str = ",".join(style_parts)
        log(f"Burning subtitles with style: {style_str}")
        
        # Escape path for ffmpeg
        # Windows/Unix path handling might be tricky in filter string
        # Using relative path or simple filename if possible, or escaping
        # For now, try absolute path with forward slashes
        # Escape single quotes and colons
        sub_path_escaped = subtitle_path.replace('\\', '/').replace(':', '\\:').replace("'", r"'\''")
        
        # Also escape [ and ] as they are special in filter graph
        sub_path_escaped = sub_path_escaped.replace('[', r'\[').replace(']', r'\]')
        
        (
            ffmpeg
            .input(video_path)
            .output(output_path, vf=f"subtitles='{sub_path_escaped}':force_style='{style_str}'")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path
    except ffmpeg.Error as e:
        log(f"FFmpeg error: {e.stderr.decode('utf8')}")
        return None

def burn_subtitle_image(image_path, subtitle_path, font_settings, output_path, margin_v=None, logger=None):
    """
    Burns subtitles into a single image.
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)

    try:
        # Construct style string (reuse logic or copy)
        style_parts = ["Alignment=2", "BorderStyle=1", "Outline=1", "Shadow=0"]
        
        if 'Fontname' in font_settings and font_settings['Fontname']:
            style_parts.append(f"Fontname={font_settings['Fontname']}")
        if 'Fontsize' in font_settings and font_settings['Fontsize']:
            style_parts.append(f"Fontsize={font_settings['Fontsize']}")
        if 'PrimaryColour' in font_settings:
            c = font_settings['PrimaryColour'].replace('#', '')
            if len(c) == 6:
                ass_color = f"&H00{c[4:6]}{c[2:4]}{c[0:2]}"
                style_parts.append(f"PrimaryColour={ass_color}")
        
        style_parts.append("OutlineColour=&H00000000")
        
        if margin_v is not None:
            style_parts.append(f"MarginV={margin_v}")
        
        style_str = ",".join(style_parts)
        
        sub_path_escaped = subtitle_path.replace('\\', '/').replace(':', '\\:').replace("'", r"'\''")
        sub_path_escaped = sub_path_escaped.replace('[', r'\[').replace(']', r'\]')
        
        (
            ffmpeg
            .input(image_path)
            .output(output_path, vf=f"subtitles='{sub_path_escaped}':force_style='{style_str}'")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path
    except ffmpeg.Error as e:
        log(f"FFmpeg error: {e.stderr.decode('utf8')}")
        return None
