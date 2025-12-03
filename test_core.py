import os
import shutil
from core.tts import generate_audio
from core.video import merge_audio_video, burn_subtitles
from core.subtitles import generate_subtitles, save_srt
from core.utils import create_manifest, generate_id

def test_pipeline():
    print("Starting pipeline test...")
    
    # Setup
    output_dir = "test_output"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    
    video_path = "dummy_video.mp4"
    if not os.path.exists(video_path):
        print("Error: dummy_video.mp4 not found")
        return

    lang_code = "en"
    text = "This is a test video. We are testing the video editor pipeline."
    
    # 1. Generate Audio
    print("1. Generating Audio...")
    audio_path = os.path.join(output_dir, "test_audio.mp3")
    generate_audio(text, lang_code, audio_path, use_gemini=True)
    if not os.path.exists(audio_path):
        print("Error: Audio generation failed")
        return
    print("Audio generated.")

    # 2. Merge Video
    print("2. Merging Video...")
    merged_path = os.path.join(output_dir, "merged.mp4")
    merge_audio_video(video_path, audio_path, merged_path)
    if not os.path.exists(merged_path):
        print("Error: Video merge failed")
        return
    print("Video merged.")

    # 3. Generate Subtitles
    print("3. Generating Subtitles...")
    subs = generate_subtitles(audio_path, language=lang_code, mode='sentence')
    srt_path = os.path.join(output_dir, "test.srt")
    save_srt(subs, srt_path)
    if not os.path.exists(srt_path):
        print("Error: Subtitle generation failed")
        return
    print(f"Subtitles generated: {len(subs)} segments")

    # 4. Burn Subtitles
    print("4. Burning Subtitles...")
    final_path = os.path.join(output_dir, "final.mp4")
    font_settings = {"Fontname": "Arial", "Fontsize": "24", "PrimaryColour": "#FFFFFF"}
    burn_subtitles(merged_path, srt_path, font_settings, final_path)
    if not os.path.exists(final_path):
        print("Error: Burn subtitles failed")
        return
    print("Subtitles burned.")

    # 5. Manifest
    print("5. Creating Manifest...")
    data = [{"id": generate_id(), "language": "English", "title": "Test Video", "file_path": final_path}]
    create_manifest(output_dir, data)
    if not os.path.exists(os.path.join(output_dir, "gemlogin_manifest.json")):
        print("Error: Manifest creation failed")
        return
    print("Manifest created.")

    print("Pipeline test completed successfully!")

if __name__ == "__main__":
    test_pipeline()
