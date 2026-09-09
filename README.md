# JARVIS

A local-first voice-activated personal assistant.

```text
Audio → wake-word detection → transcription → LLM → voice response
```

## Current structure

```text
jarvis/
├── __init__.py
├── app.py             # application entry point
└── audio/             # future audio-capture module
    └── __init__.py
```

The project uses Python 3.11 or later. There are no external dependencies yet:
audio capture will be implemented in the next step.

To verify the entry point:

```bash
python -m jarvis.app
```
