import ffmpeg
import os

def run_test(name, style_dict):
    print(f"--- Testing {name} ---")
    video_path = "debug_video.mp4"
    subtitle_path = "debug_subs.srt"
    output_path = f"debug_output_{name}.mp4"
    
    # Ensure inputs exist
    if not os.path.exists(video_path):
        os.system(f"ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=5 -c:v libx264 -t 5 {video_path}")
    if not os.path.exists(subtitle_path):
        with open(subtitle_path, 'w') as f:
            f.write("1\n00:00:01,000 --> 00:00:05,000\nTEST SUBTITLE VISIBLE?\n\n")

    # Construct style string
    style_parts = []
    for k, v in style_dict.items():
        style_parts.append(f"{k}={v}")
    style_str = ",".join(style_parts)
    
    print(f"Style: {style_str}")
    
    sub_path_escaped = subtitle_path.replace('\\', '/').replace(':', '\\:').replace("'", r"'\''")
    sub_path_escaped = sub_path_escaped.replace('[', r'\[').replace(']', r'\]')

    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_path, vf=f"subtitles='{sub_path_escaped}':force_style='{style_str}'")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print(f"Success: {output_path}")
    except ffmpeg.Error as e:
        print(f"Failed: {e.stderr.decode('utf8')}")

def main():
    # 1. Baseline (No style)
    run_test("baseline", {})
    
    # 2. Font Only
    run_test("font_arial", {"Fontname": "Arial", "Fontsize": 24})
    
    # 3. Color Only (Red)
    # &H000000FF (BGR for Red, Alpha 00)
    run_test("color_red", {"PrimaryColour": "&H000000FF", "Fontsize": 40})
    
    # 4. Margin Only
    run_test("margin_100", {"MarginV": 100, "Fontsize": 40})
    
    # 5. All Combined
    run_test("combined", {
        "Fontname": "Arial",
        "Fontsize": 40,
        "PrimaryColour": "&H000000FF",
        "MarginV": 100,
        "BorderStyle": 1,
        "Outline": 2
    })

if __name__ == "__main__":
    main()
