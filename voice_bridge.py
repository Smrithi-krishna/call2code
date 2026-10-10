"""Low-latency laptop <-> phone audio bridge for OpenAI Realtime.

The selected USB interface must be dedicated to this app:
  input  = phone headphone output -> USB line/mic input
  output = USB line/headphone output -> attenuator/isolator -> phone mic input

Use `python voice_bridge.py --list-devices` first. Never use the laptop's
default system mixer for this bridge if you want YouTube/notifications excluded.
"""
import argparse
import asyncio
import base64
import json
import os
import queue
import threading

import sounddevice as sd
import websockets

RATE = 24_000
CHANNELS = 1
BLOCK = 480  # 20 ms at 24 kHz
MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-mini")
URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"


def list_devices() -> None:
    for i, d in enumerate(sd.query_devices()):
        print(f"{i:>3}  in={d['max_input_channels']:<2} out={d['max_output_channels']:<2}  {d['name']}")


async def run(input_device: int | str, output_device: int | str) -> None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Set OPENAI_API_KEY before running.")

    loop = asyncio.get_running_loop()
    mic_chunks: asyncio.Queue[bytes] = asyncio.Queue(maxsize=20)
    speaker_chunks: queue.Queue[bytes | None] = queue.Queue(maxsize=40)

    def on_input(indata, frames, time_info, status):
        if status:
            print(f"input: {status}")
        raw = bytes(indata)
        try:
            loop.call_soon_threadsafe(mic_chunks.put_nowait, raw)
        except (asyncio.QueueFull, RuntimeError):
            pass  # drop old audio rather than increasing latency

    def play_worker():
        with sd.RawOutputStream(device=output_device, samplerate=RATE,
                                channels=CHANNELS, dtype="int16", blocksize=BLOCK) as out:
            while True:
                chunk = speaker_chunks.get()
                if chunk is None:
                    return
                out.write(chunk)

    playback = threading.Thread(target=play_worker, daemon=True)
    playback.start()

    headers = {"Authorization": f"Bearer {key}"}
    async with websockets.connect(URL, additional_headers=headers, ping_interval=20) as ws:
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": MODEL,
                "output_modalities": ["audio"],
                "instructions": (
                    "You are a concise, friendly website-planning assistant. "
                    "Ask one question at a time about the caller's business, audience, "
                    "style, pages, contact details, and desired call to action."
                ),
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": RATE},
                        "noise_reduction": {"type": "near_field"},
                        "turn_detection": {
                            "type": "server_vad", "threshold": 0.5,
                            "prefix_padding_ms": 300, "silence_duration_ms": 500
                        }
                    },
                    "output": {"format": {"type": "audio/pcm", "rate": RATE}, "voice": "marin"}
                }
            }
        }))

        async def send_audio():
            with sd.RawInputStream(device=input_device, samplerate=RATE,
                                   channels=CHANNELS, dtype="int16", blocksize=BLOCK,
                                   callback=on_input):
                while True:
                    chunk = await mic_chunks.get()
                    await ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(chunk).decode("ascii")
                    }))

        async def receive_audio():
            async for message in ws:
                event = json.loads(message)
                kind = event.get("type", "")
                if kind == "response.output_audio.delta":
                    speaker_chunks.put(base64.b64decode(event["delta"]))
                elif kind == "response.output_audio_transcript.delta":
                    print(event.get("delta", ""), end="", flush=True)
                elif kind == "response.done":
                    print()
                elif kind == "error":
                    print("\nRealtime error:", event)

        await asyncio.gather(send_audio(), receive_audio())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--input", help="PortAudio device index or exact name")
    parser.add_argument("--output", help="PortAudio device index or exact name")
    args = parser.parse_args()
    if args.list_devices:
        list_devices()
        return
    if args.input is None or args.output is None:
        raise SystemExit("Pass --input and --output. Use --list-devices first.")
    def device(value):
        return int(value) if value.isdigit() else value
    asyncio.run(run(device(args.input), device(args.output)))


if __name__ == "__main__":
    main()
