# AI Video Generation Pipeline 🎬

**Automated end-to-end pipeline that transforms a single topic into a YouTube-ready video.**

Built for the ASTRONOVA SYNERGIES LLP internship assignment.

---

## 🚀 Features

- **AI Script Generation**: Uses Google Gemini 2.5 Flash to create engaging, structured scripts
- **Natural Voiceover**: High-quality text-to-speech using Microsoft Edge TTS (free tier)
- **Stock Visuals**: Automatically fetches relevant videos/images from Pexels API
- **Automated Editing**: Syncs audio, video, and adds subtitles using MoviePy
- **YouTube Shorts Ready**: Outputs 1080x1920 portrait videos optimized for Shorts
- **SEO Metadata**: Generates titles, descriptions, and tags for better discoverability

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **AI Script** | Google Gemini 2.5 Flash API |
| **Voiceover** | Edge TTS (Microsoft) |
| **Visuals** | Pexels API |
| **Video Editing** | MoviePy + Pillow (PIL) |
| **Language** | Python 3.10+ |

---

## 📦 Installation

### Prerequisites
- Python 3.10 or higher
- FFmpeg (bundled with `imageio-ffmpeg`)

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/NeRd-StEyN/DruiDot.git
   cd DruiDot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Keys**:
   
   Rename `.env.example` to `.env` and add your keys:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   PEXELS_API_KEY=your_pexels_api_key_here
   ```

   **Get API Keys**:
   - **Gemini**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Free tier available)
   - **Pexels**: [Pexels API](https://www.pexels.com/api/new/) (Free tier available)

---

## 🎮 Usage

Run the pipeline with a topic:

```bash
python main.py "Your Video Topic Here"
```

**Example**:
```bash
python main.py "5 Mind-Blowing Facts About Space"
```

### Output
- `output_video.mp4` - Your final YouTube Shorts video (1080x1920)
- `video_metadata.json` - SEO-optimized title, description, and tags
- `assets/` - Generated audio files and downloaded visuals

---

## 📁 Project Structure

```
DruiDot/
├── main.py                    # Main pipeline orchestrator
├── requirements.txt           # Python dependencies
├── .env.example              # API key template
├── pipeline/
│   ├── script_gen.py         # AI script generation (Gemini)
│   ├── voice_gen.py          # Text-to-speech (Edge TTS)
│   ├── visual_gen.py         # Stock footage fetcher (Pexels)
│   ├── video_editor.py       # Video assembly (MoviePy)
│   ├── seo_gen.py            # SEO metadata generator
│   └── config.py             # Configuration utilities
├── assets/
│   ├── audio/                # Generated voiceovers
│   ├── video/                # Downloaded stock videos
│   └── images/               # Downloaded/placeholder images
├── output_video.mp4          # Final generated video
└── video_metadata.json       # SEO metadata
```

---

## 🎯 Pipeline Workflow

1. **Script Generation** → Gemini AI creates a JSON-structured script with scenes and visual keywords
2. **Voiceover Creation** → Edge TTS converts text to natural-sounding audio
3. **Visual Fetching** → Pexels API downloads relevant stock footage/images
4. **Video Assembly** → MoviePy combines audio, video, and subtitles
5. **SEO Generation** → Creates YouTube-optimized metadata

---

## 📝 Assignment Write-up (200 words)

### Tools Used
I built this pipeline using **Google Gemini 2.5 Flash** for AI-driven script generation, which outputs a structured JSON with scene-by-scene content and visual keywords. **Edge TTS** provides free, natural-sounding voiceovers without API limits, using the "AndrewNeural" voice. **Pexels API** supplies high-quality portrait stock footage matching the generated keywords. **MoviePy** handles all video processing—resizing to 9:16 aspect ratio, audio-video synchronization, and subtitle overlays using PIL for text rendering.

### Biggest Challenge
The most significant challenge was ensuring robust audio-video synchronization while handling varied aspect ratios from Pexels. Stock videos come in different orientations, so I implemented intelligent resizing and center-cropping to maintain a consistent 1080x1920 layout for YouTube Shorts. Additionally, parsing JSON from LLM outputs required regex-based cleaning to handle markdown code blocks. Windows console encoding issues with emoji characters also required removing all Unicode symbols from print statements.

### What I'd Improve
1. **Dynamic Transitions**: Add smooth fade/slide transitions between scenes
2. **Advanced Subtitles**: Implement word-level timing using Whisper API for viral-style captions
3. **Background Music**: Integrate royalty-free music mixing with volume ducking
4. **Thumbnail Generation**: Auto-create eye-catching thumbnails using AI image generation
5. **YouTube Auto-Upload**: Add YouTube Data API integration for one-click publishing

---

## 🎥 Demo

Run the pipeline and watch it generate a complete video in ~15-20 minutes:

```bash
python main.py "The Science Behind Dreams"
```

---

## 🤝 Contributing

This project was built as an internship assignment. Feel free to fork and extend it!

---

## 📄 License

MIT License - Feel free to use this project for learning and development.

---

## 👨‍💻 Author

**NeRd-StEyN**  
Built for ASTRONOVA SYNERGIES LLP Internship Assignment

---

## 🙏 Acknowledgments

- Google Gemini for AI script generation
- Microsoft Edge TTS for free voiceover synthesis
- Pexels for high-quality stock footage
- MoviePy community for video processing tools