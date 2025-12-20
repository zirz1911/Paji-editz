import ffmpeg
import os

def merge_audio_video(video_path, audio_path, output_path, mode="trim", music_path=None, music_volume=0.15):
    """
    Merges video and audio using ffmpeg.
    mode="trim": Cut/loop video to match TTS audio length exactly.
    mode="bg_music": Keep video length, mix TTS with looped background music.
    """
    import subprocess
    
    try:
        # Get audio duration first
        audio_duration = get_audio_duration(audio_path)
        if audio_duration is None:
            print("Could not determine audio duration")
            return None
        
        # Get video duration
        probe = ffmpeg.probe(video_path)
        video_duration = float(probe['format']['duration'])
        
        print(f"Audio duration: {audio_duration:.2f}s, Video duration: {video_duration:.2f}s")
        
        if mode == "bg_music" and music_path and os.path.exists(music_path):
            # Background Music Mode
            # Loop music, lower volume, mix with TTS
            input_video = ffmpeg.input(video_path)
            input_tts = ffmpeg.input(audio_path)
            input_music = ffmpeg.input(music_path, stream_loop=-1)
            
            music_audio = input_music.audio.filter('volume', music_volume)
            tts_audio = input_tts.audio
            
            mixed_audio = ffmpeg.filter([tts_audio, music_audio], 'amix', inputs=2, duration='longest')
            
            # Output with -shortest (to cut to video length)
            (
                ffmpeg
                .output(input_video.video, mixed_audio, output_path, vcodec='copy', acodec='aac', strict='experimental', shortest=None)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        elif mode == "bg_music":
            # User wants to keep video length, but no music provided.
            input_video = ffmpeg.input(video_path)
            input_tts = ffmpeg.input(audio_path)
            (
                ffmpeg
                .output(input_video.video, input_tts.audio, output_path, vcodec='copy', acodec='aac', strict='experimental')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        else:
            # Trim mode: Cut/loop video to match audio length exactly
            if video_duration >= audio_duration:
                # Video is longer or equal - just trim to audio length
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path,
                    '-i', audio_path,
                    '-t', str(audio_duration),
                    '-map', '0:v',
                    '-map', '1:a',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    output_path
                ]
            else:
                # Video is shorter - loop video to match audio length
                print(f"Video is shorter than audio, looping video to match {audio_duration:.2f}s")
                cmd = [
                    'ffmpeg', '-y',
                    '-stream_loop', '-1',  # Loop video infinitely
                    '-i', video_path,
                    '-i', audio_path,
                    '-t', str(audio_duration),  # Cut at audio duration
                    '-map', '0:v',
                    '-map', '1:a',
                    '-c:v', 'libx264',  # Need to re-encode when looping
                    '-preset', 'fast',
                    '-c:a', 'aac',
                    output_path
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr}")
                return None
                
        return output_path
    except ffmpeg.Error as e:
        print(f"FFmpeg error: {e.stderr.decode('utf8')}")
        return None


def create_image_video(image_path, output_path, duration=5.0, fps=30, width=1080, height=1920):
    """
    Create a video from a single image.
    
    Args:
        image_path: Path to the image file
        output_path: Output video path
        duration: Duration of the video in seconds (default 5.0s)
        fps: Frames per second for output video
        width: Video width (default 1080 for 9:16 portrait)
        height: Video height (default 1920 for 9:16 portrait)
    
    Returns:
        output_path on success, None on failure
    """
    import subprocess
    
    try:
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-t', str(duration),
            '-framerate', str(fps),
            '-i', image_path,
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-an',  # No audio
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return None
        
        return output_path
    except Exception as e:
        print(f"Error creating image video: {e}")
        return None


def create_images_to_videos(image_folder, output_folder, duration=5.0, fps=30, width=1080, height=1920, logger=None):
    """
    Create individual videos from each image in a folder.
    
    Args:
        image_folder: Path to folder containing images
        output_folder: Output folder for videos
        duration: Duration of each video in seconds (default 5.0s)
        fps: Frames per second
        width: Video width
        height: Video height
        logger: Logger function
    
    Returns:
        List of created video paths
    """
    import glob
    
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    os.makedirs(output_folder, exist_ok=True)
    
    # Find all images
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.JPEG', '*.PNG', '*.WEBP']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(image_folder, ext)))
    
    image_files = sorted(image_files)
    
    if not image_files:
        log(f"No images found in {image_folder}")
        return []
    
    log(f"Found {len(image_files)} images to process")
    
    created_videos = []
    for i, image_path in enumerate(image_files):
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        output_path = os.path.join(output_folder, f"{image_name}.mp4")
        
        log(f"Processing image {i+1}/{len(image_files)}: {os.path.basename(image_path)}")
        
        result = create_image_video(image_path, output_path, duration, fps, width, height)
        if result:
            created_videos.append(result)
            log(f"Created: {os.path.basename(output_path)}")
        else:
            log(f"Failed to process: {os.path.basename(image_path)}")
    
    return created_videos


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
                log(f"margin_v received: {margin_v}")
                
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
        # Alignment=2 (Bottom Center)
        # BorderStyle=1 (Outline) or BorderStyle=4 (Opaque box/background)
        
        # Check settings
        bg_enabled = font_settings.get('BackgroundEnabled', False)
        border_enabled = font_settings.get('BorderEnabled', True)
        
        if bg_enabled:
            # Use BorderStyle=3 for opaque box (standard ASS box)
            # Outline defines padding? No, for Style 3, Outline is NOT used for text outline usually.
            # But let's try to make it look cleaner.
            style_parts = ["Alignment=2", "BorderStyle=3", "Outline=2", "Shadow=0"]
            
            # Add background color (uses OutlineColour for the box in BorderStyle=4)
            if 'BackgroundColour' in font_settings:
                c = font_settings['BackgroundColour'].replace('#', '')
                if len(c) == 6:
                    # ASS format: &HAABBGGRR (AA = alpha, 00 = fully opaque, 80 = semi-transparent)
                    ass_bg_color = f"&H80{c[4:6]}{c[2:4]}{c[0:2]}"  # 80 = semi-transparent
                    style_parts.append(f"OutlineColour={ass_bg_color}")
                    style_parts.append(f"BackColour={ass_bg_color}")
        elif border_enabled:
            # Border/Outline style
            style_parts = ["Alignment=2", "BorderStyle=1", "Outline=2", "Shadow=1"]
            # Add black outline for contrast
            style_parts.append("OutlineColour=&H00000000")
        else:
            # No border, no background - just text
            style_parts = ["Alignment=2", "BorderStyle=1", "Outline=0", "Shadow=0"]
        
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


def get_audio_duration(audio_path):
    """
    Get the duration of an audio file in seconds using ffprobe.
    """
    try:
        probe = ffmpeg.probe(audio_path)
        duration = float(probe['format']['duration'])
        return duration
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return None


def create_slideshow_video(image_folder, audio_duration, output_path, transition_duration=0.5, fps=30, image_duration=3.0):
    """
    Create a slideshow video from images AND videos in a folder with fade transitions.
    
    Args:
        image_folder: Path to folder containing images and/or videos
        audio_duration: Target duration in seconds (from TTS audio)
        output_path: Output video path
        transition_duration: Duration of fade transition between items (default 0.5s)
        fps: Frames per second for output video
        image_duration: Duration each image is displayed in seconds (default 3.0s)
    
    Returns:
        output_path on success, None on failure
    """
    import subprocess
    import glob
    import tempfile
    
    # 9:16 aspect ratio (portrait/vertical video for TikTok, Reels, etc.)
    WIDTH = 1080
    HEIGHT = 1920
    
    try:
        # Find all media files in folder (images and videos)
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.JPEG', '*.PNG', '*.WEBP']
        video_extensions = ['*.mp4', '*.MP4', '*.mov', '*.MOV', '*.avi', '*.AVI', '*.mkv', '*.MKV']
        
        media_files = []
        
        # Collect images
        for ext in image_extensions:
            for f in glob.glob(os.path.join(image_folder, ext)):
                media_files.append({'path': f, 'type': 'image'})
        
        # Collect videos
        for ext in video_extensions:
            for f in glob.glob(os.path.join(image_folder, ext)):
                media_files.append({'path': f, 'type': 'video'})
        
        # Sort alphabetically by filename
        media_files = sorted(media_files, key=lambda x: x['path'])
        
        if not media_files:
            print(f"No images or videos found in {image_folder}")
            return None
        
        num_images = sum(1 for m in media_files if m['type'] == 'image')
        num_videos = sum(1 for m in media_files if m['type'] == 'video')
        print(f"Found {num_images} images and {num_videos} videos in {image_folder}")
        
        # Calculate total media duration and prepare clips
        # For images: use image_duration
        # For videos: use their actual duration (trimmed if necessary)
        
        display_time = max(image_duration, transition_duration + 0.1)
        
        # Calculate slots needed to fill audio duration
        effective_duration_per_slot = display_time - transition_duration
        slots_needed = int((audio_duration - transition_duration) / effective_duration_per_slot) + 1
        slots_needed = max(slots_needed, 1)
        
        # Create media list (loop if needed)
        media_list = []
        while len(media_list) < slots_needed:
            media_list.extend(media_files)
        media_list = media_list[:slots_needed]
        
        N = len(media_list)
        
        # Adjust display_time for exact audio duration fit
        if N > 1:
            display_time = (audio_duration + (N - 1) * transition_duration) / N
        else:
            display_time = audio_duration
        
        print(f"Using {N} media slots, {display_time:.2f}s each, transition: {transition_duration}s, resolution: {WIDTH}x{HEIGHT} (9:16)")
        
        # Create temporary directory for intermediate files
        temp_dir = tempfile.mkdtemp()
        temp_clips = []
        
        try:
            # Pre-process each media item to a standardized clip
            for i, media in enumerate(media_list):
                temp_clip_path = os.path.join(temp_dir, f"clip_{i:04d}.mp4")
                
                if media['type'] == 'image':
                    # Convert image to video clip
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1',
                        '-t', str(display_time),
                        '-framerate', str(fps),
                        '-i', media['path'],
                        '-vf', f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p',
                        '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p',
                        '-r', str(fps),
                        '-an',
                        temp_clip_path
                    ]
                else:
                    # Process video: scale, trim to display_time
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', media['path'],
                        '-t', str(display_time),
                        '-vf', f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,fps={fps}',
                        '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p',
                        '-r', str(fps),
                        '-an',
                        temp_clip_path
                    ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Error processing media {i}: {result.stderr}")
                    continue
                
                temp_clips.append(temp_clip_path)
            
            if not temp_clips:
                print("No clips were successfully processed")
                return None
            
            N = len(temp_clips)
            
            if N == 1:
                # Just copy the single clip
                import shutil
                shutil.copy(temp_clips[0], output_path)
            else:
                # Combine clips with xfade transitions
                input_args = []
                for clip in temp_clips:
                    input_args.extend(['-i', clip])
                
                # Build filter complex for xfade
                filter_parts = []
                offset = display_time - transition_duration
                prev_label = '0:v'
                
                for i in range(1, N):
                    next_label = f'vout{i}' if i < N - 1 else 'vfinal'
                    filter_parts.append(f'[{prev_label}][{i}:v]xfade=transition=fade:duration={transition_duration}:offset={offset:.3f}[{next_label}]')
                    prev_label = next_label
                    offset += display_time - transition_duration
                
                filter_complex = ';'.join(filter_parts)
                
                cmd = [
                    'ffmpeg', '-y',
                    *input_args,
                    '-filter_complex', filter_complex,
                    '-map', '[vfinal]',
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-r', str(fps),
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"FFmpeg error: {result.stderr}")
                    return None
            
            return output_path
            
        finally:
            # Cleanup temp files
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error creating slideshow: {e.stderr}")
        return None
    except Exception as e:
        print(f"Error creating slideshow: {e}")
        return None


def overlay_logo(video_path, logo_path, output_path, position=None, logo_scale=0.15, logger=None):
    """
    Overlay a logo image onto a video at specified position.
    
    Args:
        video_path: Path to input video
        logo_path: Path to logo image (PNG with transparency recommended)
        output_path: Path for output video
        position: Dict with 'x' and 'y' keys for logo position (default top-left)
        logo_scale: Scale factor for logo relative to video width (default 0.15 = 15%)
        logger: Logger function
    
    Returns:
        output_path on success, None on failure
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    if position is None:
        position = {"x": 50, "y": 50}
    
    try:
        # Get video dimensions
        probe = ffmpeg.probe(video_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            video_width = int(video_stream['width'])
            video_height = int(video_stream['height'])
        else:
            video_width = 1080
            video_height = 1920
        
        # Calculate logo size (as percentage of video width)
        logo_width = int(video_width * logo_scale)
        
        x = position.get("x", 50)
        y = position.get("y", 50)
        
        log(f"Overlaying logo at position ({x}, {y}) with scale {logo_scale}")
        
        # Build ffmpeg command
        input_video = ffmpeg.input(video_path)
        input_logo = ffmpeg.input(logo_path)
        
        # Scale logo and overlay
        logo_scaled = input_logo.filter('scale', logo_width, -1)
        
        # Overlay logo on video
        output = ffmpeg.overlay(input_video, logo_scaled, x=x, y=y)
        
        # Output with audio
        (
            ffmpeg
            .output(output, input_video.audio, output_path, vcodec='libx264', acodec='copy')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        return output_path
        
    except ffmpeg.Error as e:
        log(f"FFmpeg error overlaying logo: {e.stderr.decode('utf8')}")
        return None
    except Exception as e:
        log(f"Error overlaying logo: {e}")
        return None


def concatenate_videos(video_paths, output_path, logger=None):
    """
    Concatenate multiple videos into a single video file.
    
    Args:
        video_paths: List of video file paths to concatenate (in order)
        output_path: Path for the output video
        logger: Logger function
    
    Returns:
        output_path on success, None on failure
    """
    import subprocess
    import tempfile
    
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    if not video_paths:
        log("No videos to concatenate")
        return None
    
    if len(video_paths) == 1:
        # Just copy the single video
        import shutil
        shutil.copy(video_paths[0], output_path)
        return output_path
    
    try:
        # Create a temporary file list for ffmpeg concat demuxer
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for vp in video_paths:
                # Escape single quotes in path
                escaped_path = vp.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
            list_file = f.name
        
        log(f"Concatenating {len(video_paths)} videos...")
        
        # Use concat demuxer for fast concatenation
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Cleanup temp file
        try:
            os.remove(list_file)
        except:
            pass
        
        if result.returncode != 0:
            log(f"FFmpeg concat error: {result.stderr}")
            # Try re-encoding if copy fails
            log("Trying with re-encoding...")
            
            # Re-create list file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for vp in video_paths:
                    escaped_path = vp.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
                list_file = f.name
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            try:
                os.remove(list_file)
            except:
                pass
            
            if result.returncode != 0:
                log(f"FFmpeg re-encode error: {result.stderr}")
                return None
        
        log(f"Videos concatenated to: {output_path}")
        return output_path
        
    except Exception as e:
        log(f"Error concatenating videos: {e}")
        return None


def insert_overlay_with_fade(video_path, overlay_path, output_path, start_time=2.0, duration=3.0, fade_duration=0.5, logger=None):
    """
    Insert an overlay image or video into the main video with fade in/out transitions.
    
    Args:
        video_path: Path to the main video
        overlay_path: Path to the overlay image or video
        output_path: Path to save the output video
        start_time: When to start showing the overlay (in seconds)
        duration: How long to show the overlay (in seconds)
        fade_duration: Duration of fade in/out effect (in seconds)
        logger: Optional logger function
    
    Returns:
        output_path on success, None on failure
    """
    import subprocess
    
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    try:
        # Check if overlay is image or video
        ext = os.path.splitext(overlay_path)[1].lower()
        is_image = ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        
        log(f"Inserting overlay: {os.path.basename(overlay_path)}")
        log(f"Type: {'Image' if is_image else 'Video'}, Start: {start_time}s, Duration: {duration}s")
        
        # Get main video dimensions
        probe = ffmpeg.probe(video_path)
        video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        
        if is_image:
            # For images: CENTERED on black background with fade transitions
            # This replaces the main video during the insert period with centered media
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-loop', '1', '-t', str(duration), '-i', overlay_path,
                '-filter_complex',
                f"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={duration-fade_duration}:d={fade_duration}[insert];"
                f"[0:v]split[main1][main2];"
                f"[main1]trim=0:{start_time},setpts=PTS-STARTPTS[before];"
                f"[insert]setpts=PTS-STARTPTS[middle];"
                f"[main2]trim={start_time+duration},setpts=PTS-STARTPTS[after];"
                f"[before][middle][after]concat=n=3:v=1:a=0[outv]",
                '-map', '[outv]', '-map', '0:a?',
                '-c:v', 'libx264', '-c:a', 'aac',
                output_path
            ]
        else:
            # For videos: CENTERED on black background with fade transitions
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', overlay_path,
                '-filter_complex',
                f"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"trim=0:{duration},setpts=PTS-STARTPTS,"
                f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={duration-fade_duration}:d={fade_duration}[insert];"
                f"[0:v]split[main1][main2];"
                f"[main1]trim=0:{start_time},setpts=PTS-STARTPTS[before];"
                f"[main2]trim={start_time+duration},setpts=PTS-STARTPTS[after];"
                f"[before][insert][after]concat=n=3:v=1:a=0[outv]",
                '-map', '[outv]', '-map', '0:a?',
                '-c:v', 'libx264', '-c:a', 'aac',
                output_path
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            log(f"FFmpeg overlay error: {result.stderr[:500]}")
            return None
        
        log(f"Overlay inserted successfully")
        return output_path
        
    except Exception as e:
        log(f"Error inserting overlay: {e}")
        return None


def burn_subtitles_for_news(video_path, subtitle_text, output_path, mode="sentence", margin=200, color="#FFFFFF", fontsize=48, logger=None):
    """
    Generate and burn subtitles for news anchor video.
    Uses Whisper for transcription then burns to video.
    
    Args:
        video_path: Path to the video
        subtitle_text: Original script text (for reference)
        output_path: Path to save the subtitled video
        mode: "word" or "sentence" subtitle mode
        margin: Margin from bottom in pixels
        color: Hex color for subtitle text
        fontsize: Font size in pixels
        logger: Optional logger function
    
    Returns:
        output_path on success, None on failure
    """
    import subprocess
    import tempfile
    
    def log(msg):
        if logger:
            logger(msg)
        print(msg)
    
    try:
        from core.subtitles import generate_subtitles, save_srt
        
        log(f"Generating subtitles in {mode} mode...")
        log(f"Subtitle settings: margin={margin}px, color={color}, fontsize={fontsize}px")
        
        # Extract audio from video
        audio_temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        cmd = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', audio_temp]
        subprocess.run(cmd, capture_output=True)
        
        # Generate subtitles using Whisper
        segments = generate_subtitles(audio_temp, mode=mode, model_size="base")
        
        if not segments:
            log("No subtitles generated")
            os.remove(audio_temp)
            return None
        
        # Save SRT file
        srt_temp = tempfile.NamedTemporaryFile(suffix='.srt', delete=False).name
        save_srt(segments, srt_temp)
        
        log(f"Generated {len(segments)} subtitle segments")
        
        # Convert hex color to ASS format (BGR with alpha)
        # #FFFFFF -> &HFFFFFF (white)
        hex_color = color.lstrip('#')
        # Convert RGB to BGR for ASS format
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            ass_color = f"&H{b}{g}{r}"
        else:
            ass_color = "&HFFFFFF"
        
        # Burn subtitles to video
        from core.video import burn_subtitles
        
        font_settings = {
            'Fontname': 'Arial',
            'Fontsize': str(fontsize),
            'PrimaryColour': color,  # Use original hex color, burn_subtitles will convert
            'OutlineColour': '#000000',
            'Outline': '2',
            'Shadow': '1'
        }
        
        # Pass margin as separate parameter (margin_v)
        result = burn_subtitles(video_path, srt_temp, font_settings, output_path, margin_v=margin, logger=logger)
        
        # Cleanup
        os.remove(audio_temp)
        os.remove(srt_temp)
        
        return result
        
    except Exception as e:
        log(f"Error burning subtitles: {e}")
        return None
