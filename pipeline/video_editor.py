from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
import moviepy.video.fx.all as vfx
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os

def create_text_image(text, size=(1080, 1920), font_size=150):
    """Creates a highly engaging 'Hormozi-style' subtitle image with stroke/shadow."""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size) # Bold arial
    except:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        w = draw.textlength(" ".join(current_line), font=font)
        # Keep lines short for better punchiness
        if w > size[0] - 150:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    lines.append(" ".join(current_line))
    
    total_h = len(lines) * font_size * 1.3
    current_y = (size[1] - total_h) / 2
    
    # Horror styling: Creepy Blood-Red text with dark black stroke generates a chilling vibe
    text_color = (200, 0, 0) # Deep Blood Red
    stroke_color = (0, 0, 0) # Pitch black
    stroke_width = 12 # Extremely thick shadows for bold readability
    
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (size[0] - w) / 2
        
        # Draw stroke (multiple offsets)
        for adj_x in range(-stroke_width, stroke_width+1):
            for adj_y in range(-stroke_width, stroke_width+1):
                draw.text((x+adj_x, current_y+adj_y), line, font=font, fill=stroke_color)
                
        # Draw main text
        draw.text((x, current_y), line, font=font, fill=text_color)
        current_y += font_size * 1.3
        
    return np.array(img)

def create_video(scenes, voiceovers, visuals, output_file):
    """Combines voiceovers and visuals into a final video."""
    clips = []
    
    for i, scene in enumerate(scenes):
        print(f"Processing clip {i+1}...")
        audio = AudioFileClip(voiceovers[i])
        duration = audio.duration
        
        visual_path = visuals[i]
        if visual_path.endswith(('.mp4', '.mov')):
            clip = VideoFileClip(visual_path).set_duration(duration)
            # Loop video if it's shorter than audio
            if clip.duration < duration:
                clip = clip.fx(vfx.loop, duration=duration)
        else:
            clip = ImageClip(visual_path).set_duration(duration)
        
        # Resize to YouTube Shorts format (1080x1920)
        w, h = clip.size
        target_ratio = 1080 / 1920
        current_ratio = w / h
        
        if current_ratio > target_ratio:
            # Too wide, resize by height then crop width
            clip = clip.resize(height=1920)
            w_new = clip.size[0]
            clip = clip.crop(x1=(w_new - 1080) / 2, y1=0, x2=(w_new + 1080) / 2, y2=1920)
        else:
            # Too tall, resize by width then crop height
            clip = clip.resize(width=1080)
            h_new = clip.size[1]
            clip = clip.crop(x1=0, y1=(h_new - 1920) / 2, x2=1080, y2=(h_new + 1920) / 2)
        
        clip = clip.set_audio(audio)
        
        # Add subtitle using PIL
        text_img = create_text_image(scene['text'])
        txt_clip = ImageClip(text_img).set_duration(duration)
        
        video_scene = CompositeVideoClip([clip, txt_clip])
        clips.append(video_scene)
    
    print("Concatenating clips...")
    final_video = concatenate_videoclips(clips, method="compose")
    
    print(f"Writing file: {output_file}")
    final_video.write_videofile(
        output_file, 
        fps=60, # Ultra-smooth 60 fps for premium shorts
        codec="libx264", 
        audio_codec="aac", 
        bitrate="8000k", # Very high bitrate to prevent pixelation
        threads=4, 
        preset="ultrafast" # Render incredibly fast in workflows
    )
    return output_file
