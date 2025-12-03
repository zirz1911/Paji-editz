import os
from core.image_gen import draw_text_on_image

def test_left_align():
    print("Starting Left Align Verification...")
    
    if not os.path.exists("test_frame.jpg"):
        print("Error: test_frame.jpg not found.")
        return

    # Test Multi-line text with different line lengths
    text = "Short line\nThis is a much longer line that should wrap or just be long\nShort"
    # We need to simulate wrapping by providing a long text that wraps naturally
    long_text = "First line is short. Second line is very very very very very very very very long. Third line."
    
    output_path = "test_left_align.jpg"
    
    style = {
        "font_size": 60,
        "color": "#00FF00",
        "border_color": "#000000",
        "border_width": 4,
        "position": "center",
        "anchor": "mm"
    }
    
    print(f"Generating image with text: '{long_text}'")
    result = draw_text_on_image("test_frame.jpg", long_text, output_path, style)
    
    if result and os.path.exists(output_path):
        print(f"Success! Check {output_path}. The text block should be centered, but lines inside should be LEFT aligned.")
    else:
        print("Failed to generate image.")

if __name__ == "__main__":
    test_left_align()
