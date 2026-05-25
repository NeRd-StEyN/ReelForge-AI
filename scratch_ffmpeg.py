try:
    import moviepy.config as config
    print("MoviePy FFMPEG binary path:", config.get_setting("FFMPEG_BINARY"))
except Exception as e:
    print("Error:", e)

try:
    import imageio_ffmpeg
    print("ImageIO FFMPEG exe path:", imageio_ffmpeg.get_ffmpeg_exe())
except Exception as e:
    print("Error:", e)
