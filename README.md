# ReelForge AI

AI-powered short-form video pipeline for Instagram Reels and YouTube Shorts.

If you want a strong repo name, use:
- Primary recommendation: ReelForge AI
- Alternative options: ClipSmith AI, ViralReel Engine, GhostFrame Studio

## What This Project Does

Given one topic, this project can automatically:
- Generate a story-driven script from LLM prompts
- Produce natural voice narration with Edge TTS
- Fetch portrait visuals from Pexels
- Build a final 1080x1920 reel with synced rolling subtitles
- Generate SEO metadata
- Send the final video URL and caption to Make webhook for publishing flows

## Core Features

- Continuous narration mode for smooth voice flow
- Dynamic subtitles synced to spoken words (word-boundary timing)
- Improved subtitle visibility (bold font, high-contrast box)
- Visual diversity logic to avoid repeated-looking scenes
- Domain-focused topic generation with optional analytics feedback loop
- Scheduler support for multi-post daily automation

## Tech Stack

- Python 3.10+
- OpenRouter (LLM script generation)
- Edge TTS (voice synthesis)
- Pexels API (visual assets)
- MoviePy + Pillow (editing and subtitles)
- Make.com webhook (publishing handoff)

## Project Layout

```text
.
|- main.py
|- auto_scheduler.py
|- requirements.txt
|- .env.example
|- pipeline/
|  |- script_gen.py
|  |- voice_gen.py
|  |- visual_gen.py
|  |- video_editor.py
|  |- seo_gen.py
|  |- make_handler.py
|  |- insta_handler.py
|  |- feedback_loop.py
|- assets/
|  |- audio/
|  |- video/
|  |- images/
|- data/
|  |- insta_analytics_history.jsonl
```

## Quick Start

1. Clone and install:

```bash
git clone <your-repo-url>
cd <your-repo-folder>
pip install -r requirements.txt
```

2. Create env file:
- Copy .env.example to .env
- Fill required keys

3. Run one reel:

```bash
python main.py "A disturbing mystery no one solved"
```

Output files:
- output_video.mp4
- video_metadata.json

## Environment Variables

Minimum required:

```env
OPENROUTER_API_KEY=your_key
PEXELS_API_KEY=your_key
MAKE_WEBHOOK_URL=https://hook.eu1.make.com/your_webhook_id
```

Recommended quality settings:

```env
OPENROUTER_MODEL=google/gemini-2.5-flash
OPENROUTER_FALLBACK_MODELS=google/gemini-2.0-flash-001
OPENROUTER_MAX_TOKENS=2500
AUTO_CLEANUP_ASSETS=true
SINGLE_NARRATION_MODE=true
CONTENT_DOMAIN=hooked horror story
ENABLE_INSTAGRAM_ANALYTICS=false
```

Scheduling settings:

```env
REELS_PER_DAY=3
REEL_SCHEDULE_TIMES=09:00,14:00,20:00
RUN_FIRST_REEL_NOW=true
```

## Daily Automation

Scheduler mode:

```bash
python auto_scheduler.py --mode scheduler
```

Immediate batch mode:

```bash
python auto_scheduler.py --mode batch --count 2
```

## Make.com Mapping (Important)

In your Make scenario:
- Trigger: Custom Webhook
- Publishing module: Instagram for Business

Map fields from webhook output using variable picker (do not type literals):
- Video URL -> url
- Caption -> caption

If you manually type 1.caption, Make may treat it as plain text.

## How Subtitle Sync Works

- Edge TTS provides word boundary events with timestamps
- Pipeline groups words into rolling chunks
- Subtitle chunks are shown exactly when spoken
- Fallback: static scene subtitle if timestamps are unavailable

## Quality Notes

- Subtitle readability is tuned for mobile with high contrast and safe lower-third positioning
- Visual fetch selects random unseen Pexels results per run to reduce duplicates
- Continuous narration reduces choppy scene-to-scene voice transitions

## Troubleshooting

No webhook variables in Make:
- Click Run once in Make
- Trigger script again
- Open mapping field and pick webhook variables

Caption appears as 1.caption:
- Remove typed text
- Insert mapped webhook variable token for caption

Subtitles too fast/slow:
- Keep SINGLE_NARRATION_MODE=true
- Use fewer, longer scenes in script prompt (already configured)

Pexels repetition still visible:
- Increase topic specificity in visual_keyword prompts
- Run with fresh cleanup enabled

## Roadmap

- Per-word highlight karaoke caption style
- Background music with automatic ducking
- Transition templates for scene changes
- Direct platform upload adapters beyond Make

## License

MIT

## Author

Built by NeRd-StEyN for internship and production experimentation in automated short-form content systems.
