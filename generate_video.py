#!/usr/bin/env python3
"""
HeyGen + Claude Integration
----------------------------
Uses Claude (Anthropic API) to generate a video script,
then submits it to HeyGen API to create an AI avatar video.

Usage:
    python generate_video.py --topic "Your video topic here"

Environment variables required:
    ANTHROPIC_API_KEY  - Your Claude/Anthropic API key
    HEYGEN_API_KEY     - Your HeyGen API key
"""

import os
import sys
import json
import time
import argparse
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
HEYGEN_API_URL    = "https://api.heygen.com/v2/video/generate"
HEYGEN_STATUS_URL = "https://api.heygen.com/v1/video_status.get"

# HeyGen avatar & voice IDs - Mark avatar (CustomBoxAgency)
DEFAULT_AVATAR_ID = "f709e79641224f58b8e26ca2be47a900"
DEFAULT_VOICE_ID  = "edaf0455ab41498db0a72e754dfc5ccc"  # Mark - English male

# ---------------------------------------------------------------------------
# Step 1: Generate script with Claude
# ---------------------------------------------------------------------------
def generate_script(topic: str, anthropic_api_key: str) -> str:
    """Call Claude to write a short video script for the given topic."""
    headers = {
        "x-api-key": anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-opus-4-5",
        "max_tokens": 512,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Write a concise, engaging 60-second video script about: {topic}. "
                    "The script should be spoken naturally by an AI avatar. "
                    "Return only the script text with no stage directions or labels."
                ),
            }
        ],
    }
    print(f"[1/3] Generating script with Claude for topic: '{topic}'...")
    response = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    script = response.json()["content"][0]["text"].strip()
    print(f"[1/3] Script generated ({len(script)} chars).")
    return script

# ---------------------------------------------------------------------------
# Step 2: Submit video to HeyGen
# ---------------------------------------------------------------------------
def create_heygen_video(script: str, heygen_api_key: str,
                        avatar_id: str = DEFAULT_AVATAR_ID,
                        voice_id: str = DEFAULT_VOICE_ID) -> str:
    """Submit the script to HeyGen and return the video_id."""
    headers = {
        "X-Api-Key": heygen_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                    "voice_id": voice_id,
                },
            }
        ],
        "dimension": {"width": 1280, "height": 720},
    }
    print("[2/3] Submitting to HeyGen API...")
    response = requests.post(HEYGEN_API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    video_id = data["data"]["video_id"]
    print(f"[2/3] HeyGen video submitted. video_id: {video_id}")
    return video_id

# ---------------------------------------------------------------------------
# Step 3: Poll for completion
# ---------------------------------------------------------------------------
def poll_video_status(video_id: str, heygen_api_key: str,
                      max_wait: int = 300, interval: int = 15) -> str:
    """Poll HeyGen until the video is ready; return the video URL."""
    headers = {"X-Api-Key": heygen_api_key}
    params  = {"video_id": video_id}
    print(f"[3/3] Polling HeyGen for video status (up to {max_wait}s)...")
    elapsed = 0
    while elapsed < max_wait:
        resp = requests.get(HEYGEN_STATUS_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        status_data = resp.json().get("data", {})
        status = status_data.get("status", "")
        if status == "completed":
            url = status_data.get("video_url", "")
            print(f"[3/3] Video ready! URL: {url}")
            return url
        elif status == "failed":
            raise RuntimeError(f"HeyGen video generation failed: {status_data}")
        else:
            print(f"       Status: {status} - waiting {interval}s...")
            time.sleep(interval)
            elapsed += interval
    raise TimeoutError(f"Video not ready after {max_wait}s.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate a HeyGen video using Claude.")
    parser.add_argument("--topic", required=True, help="Topic for the video script")
    parser.add_argument("--avatar-id", default=DEFAULT_AVATAR_ID)
    parser.add_argument("--voice-id",  default=DEFAULT_VOICE_ID)
    args = parser.parse_args()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    heygen_key    = os.environ.get("HEYGEN_API_KEY")

    if not anthropic_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY environment variable not set.")
    if not heygen_key:
        sys.exit("ERROR: HEYGEN_API_KEY environment variable not set.")

    # Run the pipeline
    script    = generate_script(args.topic, anthropic_key)
    video_id  = create_heygen_video(script, heygen_key, args.avatar_id, args.voice_id)
    video_url = poll_video_status(video_id, heygen_key)

    # Output result
    result = {"video_id": video_id, "video_url": video_url, "script": script}
    print("\n=== Result ===")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
