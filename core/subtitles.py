import os
from faster_whisper import WhisperModel
import datetime

def format_timestamp(seconds):
    """Converts seconds to SRT timestamp format (HH:MM:SS,mmm)"""
    td = datetime.timedelta(seconds=seconds)
    # Handle milliseconds
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def generate_subtitles(audio_path, language=None, mode='sentence', model_size="tiny"):
    """
    Generates subtitles from audio using Whisper.
    mode: 'sentence' or 'word'
    """
    try:
        # Run on CPU for compatibility, or cuda if available
        # model = WhisperModel(model_size, device="cuda", compute_type="float16")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

        segments, info = model.transcribe(audio_path, word_timestamps=(mode == 'word'), language=language)
        
        subtitles = []
        if mode == 'word':
            # Flatten word segments
            all_words = []
            for segment in segments:
                for word in segment.words:
                    all_words.append({
                        "start": word.start,
                        "end": word.end,
                        "text": word.word.strip()
                    })
            
            # Adjust end times to prevent overlapping subtitles
            # Each word's end time should not exceed the next word's start time
            for i in range(len(all_words)):
                if i < len(all_words) - 1:
                    # End this word slightly before the next word starts (50ms gap)
                    next_start = all_words[i + 1]["start"]
                    gap = 0.05  # 50ms gap between words
                    if all_words[i]["end"] > next_start - gap:
                        all_words[i]["end"] = max(all_words[i]["start"] + 0.1, next_start - gap)
                subtitles.append(all_words[i])
        else:
            # Use full segments
            for segment in segments:
                subtitles.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
        
        return subtitles
    except Exception as e:
        print(f"Error generating subtitles: {e}")
        return []

def save_srt(subtitles, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(subtitles, 1):
            start = format_timestamp(sub['start'])
            end = format_timestamp(sub['end'])
            text = sub['text']
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")
    return output_path
