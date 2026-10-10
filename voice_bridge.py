"""Low-latency laptop <-> phone audio bridge for Call2Code.

Connect the phone to your laptop via USB-C (or a dedicated USB audio interface):
  input  = phone headphone/line output -> USB mic/line input (receives caller's voice)
  output = USB headphone/line output -> phone mic/headset input (sends AI voice to caller)

AUTOMATIC CALL DETECTION:
  When run with `--auto` (or by default), it monitors the USB-C audio line continuously.
  As soon as an incoming call arrives (ringing or caller speaking), it turns on automatically,
  answers the call, converses with the caller, transcribes their spoken words live,
  generates a custom website with Kimi K3, and deploys it live to this PC's Vercel account!
"""
import argparse
import asyncio
import base64
import json
import math
import os
import queue
import struct
import sys
import threading
import time
import urllib.request
import urllib.error

import sounddevice as sd
import websockets

RATE = 24_000
CHANNELS = 1
BLOCK = 480  # 20 ms at 24 kHz
MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")
URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"
API_BASE = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")

# Audio energy thresholds
WAKE_RMS_THRESHOLD = 0.015    # RMS level indicating incoming call sound/voice
CALL_SILENCE_TIMEOUT = 7.0     # Seconds of silence after conversation to consider call completed


def list_devices() -> None:
    print("\n--- Available Audio Devices ---")
    for i, d in enumerate(sd.query_devices()):
        print(f"{i:>3}  in={d['max_input_channels']:<2} out={d['max_output_channels']:<2}  {d['name']}")
    print("--------------------------------\n")


def find_usb_devices() -> tuple[int | None, int | None]:
    """Auto-detect USB audio devices for input and output."""
    in_idx, out_idx = None, None
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        name = d['name'].lower()
        if 'usb' in name:
            if d['max_input_channels'] > 0 and in_idx is None:
                in_idx = i
            if d['max_output_channels'] > 0 and out_idx is None:
                out_idx = i

    # Fallback to defaults if no explicit USB device name found
    if in_idx is None:
        try:
            in_idx = sd.default.device[0]
        except Exception:
            pass
    if out_idx is None:
        try:
            out_idx = sd.default.device[1]
        except Exception:
            pass
    return in_idx, out_idx


def compute_rms(raw_bytes: bytes) -> float:
    """Calculate Root Mean Square (RMS) volume of 16-bit PCM audio."""
    if not raw_bytes:
        return 0.0
    count = len(raw_bytes) // 2
    shorts = struct.unpack(f"<{count}h", raw_bytes)
    sum_squares = sum((s / 32768.0) ** 2 for s in shorts)
    return math.sqrt(sum_squares / count) if count > 0 else 0.0


async def deploy_website(transcript: list[dict[str, str]]) -> str | None:
    """Send call transcript to Call2Code backend to build and deploy website via Kimi K3."""
    if not transcript:
        return None
    try:
        print("\n" + "="*60)
        print("🛠️  BUILDING TAILORED WEBSITE WITH KIMI K3...")
        print("="*60)

        # 1. Create project
        req1 = urllib.request.Request(
            f"{API_BASE}/api/projects",
            data=json.dumps({"transcript": transcript}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req1, timeout=15) as resp:
            proj = json.loads(resp.read().decode("utf-8"))

        proj_id = proj.get("id")
        if not proj_id:
            print("Failed to create project in backend.")
            return None

        print(f"Project ID: {proj_id}")
        print("Generating code with Kimi K3 & deploying to this PC's Vercel account...")

        # 2. Generate and deploy
        req2 = urllib.request.Request(
            f"{API_BASE}/api/projects/{proj_id}/generate",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req2, timeout=60) as resp:
            gen = json.loads(resp.read().decode("utf-8"))

        url = gen.get("deploymentUrl")
        if url:
            print("\n" + "🎉"*20)
            print("WEBSITE IS LIVE ON THIS PC'S VERCEL ACCOUNT!")
            print(f"👉 URL: {url}")
            print("🎉"*20 + "\n")
            return url
        else:
            print(f"Deployment issue: {gen.get('error')}")
    except Exception as e:
        print(f"Website generation/deployment error: {e}")
    return None


async def handle_call_session(input_device: int | str, output_device: int | str) -> None:
    """Handles an active phone conversation session with the caller."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("Set OPENAI_API_KEY before running.")
        return

    loop = asyncio.get_running_loop()
    mic_chunks: asyncio.Queue[bytes] = asyncio.Queue(maxsize=30)
    speaker_chunks: queue.Queue[bytes | None] = queue.Queue(maxsize=50)
    transcript: list[dict[str, str]] = []

    last_user_speech_time = [time.time()]
    conversation_active = [False]

    def on_input(indata, frames, time_info, status):
        raw = bytes(indata)
        rms = compute_rms(raw)
        if rms > WAKE_RMS_THRESHOLD:
            last_user_speech_time[0] = time.time()
        try:
            loop.call_soon_threadsafe(mic_chunks.put_nowait, raw)
        except (asyncio.QueueFull, RuntimeError):
            pass

    def play_worker():
        with sd.RawOutputStream(
            device=output_device, samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=BLOCK
        ) as out:
            while True:
                chunk = speaker_chunks.get()
                if chunk is None:
                    return
                out.write(chunk)

    playback = threading.Thread(target=play_worker, daemon=True)
    playback.start()

    headers = {"Authorization": f"Bearer {key}"}
    print(f"\n📞 Answering incoming call automatically on USB bridge...")

    try:
        async with websockets.connect(URL, additional_headers=headers, ping_interval=20) as ws:
            # Configure OpenAI Realtime session with Whisper transcription
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "model": MODEL,
                    "instructions": (
                        "You are Call2Code, an AI answering a phone call from a business owner. "
                        "Greet them warmly: 'Hi! I'm Call2Code. Tell me your business name, what you do, "
                        "and what kind of website you'd like.' "
                        "Ask one short, friendly follow-up question to learn their style and primary call to action. "
                        "When they finish describing their business, say: 'Got it! I am building your website now.' "
                        "Keep your responses concise and natural for a phone call."
                    ),
                    "voice": "alloy",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 600
                    }
                }
            }))

            # Trigger opening AI greeting immediately upon call connection
            await ws.send(json.dumps({"type": "response.create"}))
            print("🟢 Call answered! AI is speaking to caller.")

            async def send_audio():
                with sd.RawInputStream(
                    device=input_device, samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=BLOCK,
                    callback=on_input
                ):
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

                    elif kind == "conversation.item.input_audio_transcription.completed":
                        caller_text = event.get("transcript", "").strip()
                        if caller_text:
                            conversation_active[0] = True
                            last_user_speech_time[0] = time.time()
                            print(f"\n👤 Person's words: \"{caller_text}\"")
                            transcript.append({"role": "user", "text": caller_text})

                    elif kind == "response.output_audio_transcript.delta":
                        print(event.get("delta", ""), end="", flush=True)

                    elif kind == "response.output_audio_transcript.done":
                        ai_text = event.get("transcript", "").strip()
                        if ai_text:
                            transcript.append({"role": "assistant", "text": ai_text})

                    elif kind == "response.done":
                        print()

                    elif kind == "error":
                        print("\n⚠️ Realtime error:", event)

            async def silence_monitor():
                """Monitors for call completion via silence after user has spoken."""
                while True:
                    await asyncio.sleep(1.0)
                    if conversation_active[0]:
                        silence_duration = time.time() - last_user_speech_time[0]
                        if silence_duration >= CALL_SILENCE_TIMEOUT and len(transcript) >= 2:
                            print(f"\n⏳ Call completed ({CALL_SILENCE_TIMEOUT:.0f}s silence detected).")
                            break

            send_task = asyncio.create_task(send_audio())
            receive_task = asyncio.create_task(receive_audio())
            monitor_task = asyncio.create_task(silence_monitor())

            done, pending = await asyncio.wait(
                [send_task, receive_task, monitor_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()

    except Exception as e:
        print(f"Session error: {e}")
    finally:
        speaker_chunks.put(None)
        if transcript:
            print("\n📋 Finished phone transcript:")
            for item in transcript:
                print(f"  {item['role']}: {item['text']}")
            await deploy_website(transcript)


async def auto_listener(input_device: int | str, output_device: int | str) -> None:
    """Continuous daemon: listens on USB cable and turns on automatically when call comes."""
    print("\n" + "="*60)
    print("🎧 CALL2CODE AUTOMATIC CALL DETECTOR ACTIVE")
    print(f"Input:  Device #{input_device}")
    print(f"Output: Device #{output_device}")
    print("="*60)
    print("👂 Listening on USB-C audio cable... Waiting for incoming call...")

    loop = asyncio.get_running_loop()
    wake_event = asyncio.Event()

    def standby_callback(indata, frames, time_info, status):
        raw = bytes(indata)
        rms = compute_rms(raw)
        if rms > WAKE_RMS_THRESHOLD:
            loop.call_soon_threadsafe(wake_event.set)

    while True:
        wake_event.clear()
        with sd.RawInputStream(
            device=input_device, samplerate=RATE, channels=CHANNELS, dtype="int16", blocksize=BLOCK,
            callback=standby_callback
        ):
            await wake_event.wait()

        print("\n⚡ AUDIO DETECTED! Incoming call ringing or answered.")
        await asyncio.sleep(0.5)  # Short stabilization pause
        await handle_call_session(input_device, output_device)

        print("\n👂 Returning to standby... Waiting for next incoming call...")
        await asyncio.sleep(2.0)


def main():
    parser = argparse.ArgumentParser(description="Call2Code Automatic Phone Audio Bridge over USB-C")
    parser.add_argument("--list-devices", action="store_true", help="List audio input and output devices")
    parser.add_argument("--input", help="PortAudio input device index (USB-C line/mic in)")
    parser.add_argument("--output", help="PortAudio output device index (USB-C line/headphone out)")
    parser.add_argument("--manual", action="store_true", help="Run single manual session instead of automatic daemon")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    in_dev = args.input
    out_dev = args.output

    if in_dev is None or out_dev is None:
        auto_in, auto_out = find_usb_devices()
        in_dev = in_dev or auto_in
        out_dev = out_dev or auto_out

    if in_dev is None or out_dev is None:
        list_devices()
        raise SystemExit("Could not auto-detect audio devices. Pass --input and --output.")

    def parse_dev(val: int | str) -> int | str:
        return int(val) if str(val).isdigit() else val

    in_dev = parse_dev(in_dev)
    out_dev = parse_dev(out_dev)

    try:
        if args.manual:
            asyncio.run(handle_call_session(in_dev, out_dev))
        else:
            asyncio.run(auto_listener(in_dev, out_dev))
    except KeyboardInterrupt:
        print("\nCall bridge stopped by user.")


if __name__ == "__main__":
    main()
