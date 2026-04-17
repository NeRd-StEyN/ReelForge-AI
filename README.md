# AI Video Generation Pipeline 🎬

**Automated end-to-end pipeline that transforms a single topic into a YouTube-ready video.**

Built for the ASTRONOVA SYNERGIES LLP internship assignment.

---

## 🚀 Features

- **AI Script Generation**: Uses OpenRouter with Gemini models to create engaging, structured scripts
- **Natural Voiceover**: High-quality text-to-speech using Microsoft Edge TTS (free tier)
- **Stock Visuals**: Automatically fetches relevant videos/images from Pexels API
- **Automated Editing**: Syncs audio, video, and adds subtitles using MoviePy
- **YouTube Shorts Ready**: Outputs 1080x1920 portrait videos optimized for Shorts
- **SEO Metadata**: Generates titles, descriptions, and tags for better discoverability

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **AI Script** | OpenRouter (Gemini models) |
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
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   OPENROUTER_MODEL=google/gemini-2.5-flash
   OPENROUTER_FALLBACK_MODELS=google/gemini-2.0-flash-001
   OPENROUTER_MAX_TOKENS=2500
   PEXELS_API_KEY=your_pexels_api_key_here
   MAKE_WEBHOOK_URL=https://hook.eu1.make.com/your_webhook_id
   ```

   **Get API Keys**:
   - **OpenRouter**: [OpenRouter Keys](https://openrouter.ai/keys)
   - **Pexels**: [Pexels API](https://www.pexels.com/api/new/) (Free tier available)
   - **Make Webhook**: Create a Custom Webhook module in Make and copy its URL

### Make.com Reel Auto-Upload Mapping

If your Make scenario uses Webhooks -> Instagram for Business (Facebook login), map these fields from the webhook payload:

- `Video URL` -> `1.url`
- `Caption` -> `1.modifications.Subtitles` + newline + `1.text`

The pipeline now uploads your local MP4 to a temporary public URL and sends this JSON structure automatically.

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

## Instagram Growth Automation (2-3 Reels/Day)

Set these fields in your `.env`:

```env
MAKE_WEBHOOK_URL=https://hook.eu1.make.com/your_webhook_id
INSTA_USERNAME=your_instagram_username
INSTA_PASSWORD=your_instagram_password
CONTENT_DOMAIN=hooked horror story
REELS_PER_DAY=3
REEL_SCHEDULE_TIMES=09:00,14:00,20:00
RUN_FIRST_REEL_NOW=true
```

Run continuous daily automation:

```bash
python auto_scheduler.py --mode scheduler
```

Run an immediate test batch (for example 2 reels now):

```bash
python auto_scheduler.py --mode batch --count 2
```

How feedback improves content over time:

- Recent reel analytics are fetched from Instagram
- Snapshots are stored in `data/insta_analytics_history.jsonl`
- New topics are generated inside your chosen domain using recent winners
- Future scripts adapt to what already gets better reach

## 24/7 Automation Without Laptop (GitHub Actions)

This repo now includes [auto-reels workflow](.github/workflows/auto-reels.yml) that runs on GitHub servers at fixed times daily, so your laptop can stay OFF.

One-time setup:

1. Push this project to your GitHub repository.
2. In GitHub, open: Settings -> Secrets and variables -> Actions.
3. Add repository secrets:
   - `OPENROUTER_API_KEY`
   - `OPENROUTER_MODEL` (example: `google/gemini-2.5-flash`)
   - `OPENROUTER_FALLBACK_MODELS` (optional, comma-separated)
   - `PEXELS_API_KEY`
   - `MAKE_WEBHOOK_URL`
   - `CONTENT_DOMAIN` (example: `hooked horror story`)
4. Ensure your Make scenario is ON and set to trigger immediately on webhook.

After this one-time setup, posting is automatic from GitHub infrastructure.

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