import os
import tempfile
import subprocess
import json
from core.subtitles import generate_subtitles, save_srt
from core.translation import translate_text
from core.tts import generate_audio
from core.video import burn_subtitles, merge_audio_video


def get_video_dimensions(video_path):
    """
    Get video width and height using ffprobe.
    Returns (width, height) or (None, None) on error.
    """
    try:
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-select_streams', 'v:0',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get('streams'):
                stream = data['streams'][0]
                return int(stream['width']), int(stream['height'])
    except Exception as e:
        print(f"Error getting video dimensions: {e}")
    return None, None


def add_letterbox_if_horizontal(video_path, output_path, target_height=1920, logger=None):
    """
    If video is horizontal (landscape), add black bars to make it vertical (9:16).
    Centers the video vertically with black bars on top and bottom.

    Args:
        video_path: Input video path
        output_path: Output video path
        target_height: Target height for vertical video (default 1920 for 1080x1920)
        logger: Optional logger function

    Returns:
        output_path if processed, video_path if no processing needed, None on error
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)

    width, height = get_video_dimensions(video_path)
    if not width or not height:
        log("Could not determine video dimensions, skipping letterbox")
        return video_path

    log(f"Video dimensions: {width}x{height}")

    # Check if horizontal (landscape)
    if width <= height:
        log("Video is vertical/square, no letterboxing needed")
        return video_path

    log("Video is horizontal, adding letterbox for vertical format...")

    # Calculate new dimensions (9:16 aspect ratio)
    # Keep original width, calculate new height to be 16:9 inverted
    new_width = width
    new_height = int(width * 16 / 9)

    # Ensure height is even (required by some codecs)
    if new_height % 2 != 0:
        new_height += 1

    log(f"New canvas size: {new_width}x{new_height}")

    # Calculate padding (center the video)
    pad_top = (new_height - height) // 2
    pad_bottom = new_height - height - pad_top

    log(f"Padding: top={pad_top}px, bottom={pad_bottom}px")

    try:
        # FFmpeg command to add black bars
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', f'pad={new_width}:{new_height}:0:{pad_top}:black',
            '-c:a', 'copy',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            log(f"FFmpeg letterbox error: {result.stderr}")
            return None

        log(f"Letterbox applied successfully")
        return output_path

    except Exception as e:
        log(f"Error adding letterbox: {e}")
        return None


def extract_audio_from_video(video_path, output_audio_path):
    """
    Extract audio from video file to WAV format for transcription.
    """
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            output_audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg audio extraction error: {result.stderr}")
            return None
        return output_audio_path
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return None


def translate_video_subtitles(video_path, target_language, api_key, output_video_path=None,
                               font_settings=None, margin_v=None, sub_mode='sentence', logger=None):
    """
    Mode 1: Subtitle-only translation

    Args:
        sub_mode: 'sentence' for sentence-level or 'word' for word-level subtitles
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)

    try:
        log("=== Starting Subtitle Translation Mode ===")
        log(f"Target Language: {target_language}")
        log(f"Subtitle Mode: {sub_mode}")

        if not output_video_path:
            base, ext = os.path.splitext(video_path)
            output_video_path = f"{base}_subtitled_{target_language}{ext}"

        if not font_settings:
            font_settings = {
                'Fontname': 'Arial',
                'Fontsize': '48',
                'PrimaryColour': '#FFFFFF'
            }

        log("Step 1/5: Extracting audio from video...")
        audio_temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        audio_result = extract_audio_from_video(video_path, audio_temp)

        if not audio_result:
            log("Failed to extract audio from video")
            return None

        log("Step 2/5: Transcribing audio with Whisper...")
        segments = generate_subtitles(audio_temp, mode=sub_mode, model_size='base')

        if not segments:
            log("Failed to generate subtitles")
            os.remove(audio_temp)
            return None

        log(f"Generated {len(segments)} subtitle segments")

        log(f"Step 3/5: Translating subtitles to {target_language}...")
        translated_segments = []

        for i, segment in enumerate(segments):
            original_text = segment['text']
            log(f"Translating segment {i+1}/{len(segments)}: {original_text[:50]}...")

            translated_text = translate_text(original_text, target_language, api_key)

            if translated_text:
                translated_segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': translated_text
                })
            else:
                translated_segments.append(segment)

        log("Step 4/5: Applying letterbox if horizontal video...")
        letterbox_temp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name
        letterbox_result = add_letterbox_if_horizontal(video_path, letterbox_temp, logger=logger)

        # Determine which video to use for subtitle burning
        if letterbox_result and letterbox_result != video_path:
            video_for_subs = letterbox_result
            need_cleanup_letterbox = True
        else:
            video_for_subs = video_path
            need_cleanup_letterbox = False
            if os.path.exists(letterbox_temp):
                os.remove(letterbox_temp)

        log("Step 5/5: Burning translated subtitles to video...")
        srt_temp = tempfile.NamedTemporaryFile(suffix='.srt', delete=False).name
        save_srt(translated_segments, srt_temp)

        result = burn_subtitles(video_for_subs, srt_temp, font_settings, output_video_path,
                                margin_v=margin_v, logger=logger)

        os.remove(audio_temp)
        os.remove(srt_temp)
        if need_cleanup_letterbox and os.path.exists(letterbox_temp):
            os.remove(letterbox_temp)

        if result:
            log(f"Subtitle translation completed: {output_video_path}")

        return result

    except Exception as e:
        log(f"Error in subtitle translation: {e}")
        return None


def translate_video_dubbing(video_path, target_language, api_key, output_video_path=None,
                            voice="Puck", speech_speed=1.0, voice_prompt="",
                            add_subtitles=False, font_settings=None, margin_v=None,
                            sub_mode='sentence', logger=None):
    """
    Mode 2: Full dubbing (translate audio + replace)

    Args:
        sub_mode: 'sentence' for sentence-level or 'word' for word-level subtitles
    """
    def log(msg):
        if logger:
            logger(msg)
        print(msg)

    try:
        log("=== Starting Full Dubbing Mode ===")
        log(f"Target Language: {target_language}")
        log(f"Voice: {voice}, Speed: {speech_speed}x")
        log(f"Subtitle Mode: {sub_mode}")

        if not output_video_path:
            base, ext = os.path.splitext(video_path)
            output_video_path = f"{base}_dubbed_{target_language}{ext}"

        log("Step 1/6: Extracting audio from video...")
        audio_temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        audio_result = extract_audio_from_video(video_path, audio_temp)

        if not audio_result:
            log("Failed to extract audio from video")
            return None

        log("Step 2/6: Transcribing audio with Whisper...")
        segments = generate_subtitles(audio_temp, mode='sentence', model_size='base')

        if not segments:
            log("Failed to generate subtitles")
            os.remove(audio_temp)
            return None

        log(f"Generated {len(segments)} subtitle segments")

        log(f"Step 3/6: Translating text to {target_language}...")
        full_text = " ".join([seg['text'] for seg in segments])

        translated_full_text = translate_text(full_text, target_language, api_key)

        if not translated_full_text:
            log("Translation failed")
            os.remove(audio_temp)
            return None

        log(f"Translated text: {translated_full_text[:100]}...")

        log(f"Step 4/6: Generating TTS audio in {target_language}...")
        tts_audio_temp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name

        tts_result = generate_audio(
            translated_full_text,
            target_language,
            tts_audio_temp,
            voice=voice,
            api_key=api_key,
            speech_speed=speech_speed,
            voice_prompt=voice_prompt
        )

        if not tts_result:
            log("Failed to generate TTS audio")
            os.remove(audio_temp)
            return None

        log("Step 5/6: Applying letterbox if horizontal video...")
        letterbox_temp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name
        letterbox_result = add_letterbox_if_horizontal(video_path, letterbox_temp, logger=logger)

        # Determine which video to use
        if letterbox_result and letterbox_result != video_path:
            video_for_merge = letterbox_result
            need_cleanup_letterbox = True
        else:
            video_for_merge = video_path
            need_cleanup_letterbox = False
            if os.path.exists(letterbox_temp):
                os.remove(letterbox_temp)

        log("Step 6/6: Replacing audio in video...")
        video_with_new_audio_temp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name

        merge_result = merge_audio_video(
            video_for_merge,
            tts_audio_temp,
            video_with_new_audio_temp,
            mode="trim"
        )

        if not merge_result:
            log("Failed to merge video with new audio")
            os.remove(audio_temp)
            os.remove(tts_audio_temp)
            return None

        if add_subtitles:
            log("Adding translated subtitles to dubbed video...")

            if not font_settings:
                font_settings = {
                    'Fontname': 'Arial',
                    'Fontsize': '48',
                    'PrimaryColour': '#FFFFFF'
                }

            new_segments = generate_subtitles(tts_audio_temp, language=target_language,
                                              mode=sub_mode, model_size='base')

            if new_segments:
                srt_temp = tempfile.NamedTemporaryFile(suffix='.srt', delete=False).name
                save_srt(new_segments, srt_temp)

                final_result = burn_subtitles(
                    video_with_new_audio_temp,
                    srt_temp,
                    font_settings,
                    output_video_path,
                    margin_v=margin_v,
                    logger=logger
                )

                os.remove(srt_temp)
                os.remove(video_with_new_audio_temp)
            else:
                import shutil
                shutil.move(video_with_new_audio_temp, output_video_path)
                final_result = output_video_path
        else:
            import shutil
            shutil.move(video_with_new_audio_temp, output_video_path)
            final_result = output_video_path

        os.remove(audio_temp)
        os.remove(tts_audio_temp)
        if need_cleanup_letterbox and os.path.exists(letterbox_temp):
            os.remove(letterbox_temp)

        if final_result:
            log(f"Full dubbing completed: {output_video_path}")

        return final_result

    except Exception as e:
        log(f"Error in full dubbing: {e}")
        return None


def translate_video(video_path, target_language, api_key, mode="subtitle", **kwargs):
    """
    Main entry point for video translation.

    Args:
        video_path: Path to input video
        target_language: Target language code
        api_key: Gemini API key
        mode: "subtitle" for subtitle-only, "dubbing" for full dubbing
        **kwargs: Additional arguments passed to specific translation functions

    Returns:
        output_video_path on success, None on failure
    """
    if mode == "subtitle":
        return translate_video_subtitles(video_path, target_language, api_key, **kwargs)
    elif mode == "dubbing":
        return translate_video_dubbing(video_path, target_language, api_key, **kwargs)
    else:
        print(f"Unknown translation mode: {mode}")
        return None
