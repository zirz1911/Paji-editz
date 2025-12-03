import ffmpeg
import os

def debug_burn_subtitles(video_path, subtitle_path, output_path, margin_v=50):
    print(f"Video: {video_path}")
    print(f"Subtitle: {subtitle_path}")
    
    # Create a dummy subtitle if not exists
    if not os.path.exists(subtitle_path):
        with open(subtitle_path, 'w') as f:
            f.write("1\n00:00:01,000 --> 00:00:05,000\nHello World Testing Subtitles\n\n")

    # Create dummy video if not exists
    if not os.path.exists(video_path):
        os.system(f"ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=5 -c:v libx264 -t 5 {video_path}")

    # Style
    style_str = f"Fontname=Arial,Fontsize=24,PrimaryColour=&H00FFFFFF,MarginV={margin_v}"
    
    # Path escaping
    # Try the current logic
    sub_path_escaped = subtitle_path.replace('\\', '/').replace(':', '\\:')
    
    print(f"Escaped Path: {sub_path_escaped}")
    print(f"Style: {style_str}")
    
    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_path, vf=f"subtitles='{sub_path_escaped}':force_style='{style_str}'")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print("FFmpeg run successful.")
    except ffmpeg.Error as e:
        print("FFmpeg Error!")
        print(e.stderr.decode('utf8'))

if __name__ == "__main__":
    debug_burn_subtitles("debug_video.mp4", "debug_subs.srt", "debug_output.mp4")
