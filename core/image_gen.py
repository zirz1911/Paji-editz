from PIL import Image, ImageDraw, ImageFont
import os

def draw_text_on_image(image_path, text, output_path, style):
    """
    Draws text on an image with given style.
    style: {
        "font_size": int,
        "color": str (hex),
        "border_color": str (hex),
        "border_width": int,
        "position": (x, y) tuple or "center",
        "font_path": str (optional)
    }
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGBA for transparency support if needed
            img = img.convert("RGBA")
            
            draw = ImageDraw.Draw(img)
            
            # Load Font
            font_size = style.get("font_size", 50)
            font_path = style.get("font_path", "Arial") # Default to Arial if not found
            
            try:
                font = ImageFont.truetype(font_path, font_size)
            except IOError:
                # Fallback to default
                try:
                    font = ImageFont.truetype("Arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
            
            # Text Wrapping Logic
            img_width, img_height = img.size
            max_width = img_width - 40 # Margin
            
            lines = []
            words = text.split()
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
                if w <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        # Word itself is too long, force split or just add it
                        lines.append(word)
                        current_line = []
            if current_line:
                lines.append(' '.join(current_line))
            
            # Calculate total height of block
            line_heights = []
            total_text_height = 0
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                h = bbox[3] - bbox[1]
                # Add some line spacing
                h += font_size * 0.2
                line_heights.append(h)
                total_text_height += h
            
            # Remove last spacing
            if line_heights:
                total_text_height -= (font_size * 0.2)

            # Position Block
            pos = style.get("position", "center")
            anchor = style.get("anchor", None)
            
            # Determine starting Y based on anchor/position
            # If anchor is 'mm' (center), pos is center of block
            # If anchor is None (top-left), pos is top-left of block
            
            if pos == "center":
                start_x = img_width / 2
                start_y = (img_height - total_text_height) / 2
                draw_anchor = "mm" # Force center alignment for lines
            else:
                start_x, start_y = pos
                draw_anchor = anchor
            
            # If anchor is 'mm', start_y is the center of the BLOCK.
            # We need to calculate the top of the block to draw lines downwards.
            if draw_anchor == "mm":
                current_y = start_y - (total_text_height / 2)
                # Also x is center of the BLOCK.
                # To align LEFT, we need the left edge of the block.
                # We need the max width of the lines to find the left edge.
                max_line_width = 0
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    w = bbox[2] - bbox[0]
                    if w > max_line_width:
                        max_line_width = w
                
                # Left edge relative to center start_x
                block_left_x = start_x - (max_line_width / 2)
                line_x = block_left_x
            else:
                # Assume top-left or similar. 
                # If anchor is None, it means top-left.
                current_y = start_y
                line_x = start_x
                
            # Colors
            text_color = style.get("color", "#FFFFFF")
            border_color = style.get("border_color", "#000000")
            border_width = style.get("border_width", 2)
            
            # Draw Each Line
            for i, line in enumerate(lines):
                h = line_heights[i]
                
                if draw_anchor == "mm":
                    # We are drawing left-aligned lines, but the block is centered.
                    # We calculated line_x as the left edge.
                    # We should use anchor="lm" (Left-Middle) for each line to align them to line_x.
                    # And we need the Y center of the line slot.
                    
                    line_content_h = h - (font_size * 0.2)
                    draw_y = current_y + (line_content_h / 2)
                    
                    if border_width > 0:
                        draw.text((line_x, draw_y), line, font=font, fill=text_color, stroke_width=border_width, stroke_fill=border_color, anchor="lm")
                    else:
                        draw.text((line_x, draw_y), line, font=font, fill=text_color, anchor="lm")
                        
                    current_y += h
                else:
                    # Left aligned (default)
                    # We draw at line_x, current_y
                    # anchor=None means top-left (la)
                    
                    if border_width > 0:
                        draw.text((line_x, current_y), line, font=font, fill=text_color, stroke_width=border_width, stroke_fill=border_color, anchor=draw_anchor)
                    else:
                        draw.text((line_x, current_y), line, font=font, fill=text_color, anchor=draw_anchor)
                    
                    current_y += h
            
            # Save
            img = img.convert("RGB") # Convert back to RGB for JPG
            img.save(output_path)
            return output_path
            
    except Exception as e:
        print(f"Image Gen Error: {e}")
        return None
