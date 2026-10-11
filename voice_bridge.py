"""Low-latency laptop <-> phone audio bridge for Call2Code (Supports Realme 6 Pro & USB/Bluetooth Phone calls in English).

Connect your phone to your laptop:
  - Direct USB-C cable (Realme UI: Enable USB Debugging in Developer Options)
  - Or Windows Phone Link / Bluetooth Hands-Free (e.g. Reuben's phone)

AUTOMATIC ENGLISH PHONE CALL WORKFLOW:
  1. The bridge continuously monitors the phone audio connection in low-power standby.
  2. When an incoming call arrives (ringing or caller speaking), it turns on automatically.
  3. It greets the caller in natural, professional English:
     "Hello! I am Call2Code, your AI website builder. What is your business called, and what products or services do you offer?"
  4. It listens to spoken English live, logs the caller's words in real time:
     👤 Person's words: "..."
  5. When the caller hangs up or finishes talking, it automatically builds the website with Kimi K3
     and deploys it live to this PC's Vercel account!
"""
import argparse
import asyncio
import base64
import json
import math
import os
import queue
import struct
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

try:
    import msvcrt
except ImportError:
    msvcrt = None

ADB_PATH = r"C:\Users\andre\AppData\Local\Android\Sdk\platform-tools\adb.exe"

def get_adb_call_state() -> int | None:
    """Return Android telephony call state: 0=IDLE, 1=RINGING (incoming call), 2=OFFHOOK (active call)."""
    if not os.path.exists(ADB_PATH):
        return None
    try:
        res = subprocess.run(
            [ADB_PATH, "shell", "dumpsys", "telephony.registry"],
            capture_output=True, text=True, timeout=1.5
        )
        for line in res.stdout.splitlines():
            if "mCallState" in line:
                val = line.split("=")[-1].strip()
                if val.isdigit():
                    return int(val)
    except Exception:
        pass
    return None

def answer_adb_call() -> bool:
    """Automatically answer incoming phone call on Realme 6 Pro over USB-C."""
    if not os.path.exists(ADB_PATH):
        return False
    try:
        subprocess.run([ADB_PATH, "shell", "telecom", "accept-ringing-call"], timeout=2.0)
        return True
    except Exception:
        try:
            subprocess.run([ADB_PATH, "shell", "input", "keyevent", "KEYCODE_HEADSETHOOK"], timeout=2.0)
            return True
        except Exception:
            return False

# Ensure UTF-8 console output for Malayalam and emojis on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Auto-load .env file if environment variables aren't already exported
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v

import numpy as np
import sounddevice as sd
import websockets

OAI_RATE = 24_000
CHANNELS = 1
MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-mini")
URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"
API_BASE = os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000")

# Audio energy thresholds
WAKE_RMS_THRESHOLD = 0.015    # RMS level indicating incoming call sound/voice
CALL_SILENCE_TIMEOUT = 7.0     # Seconds of silence after conversation to consider call completed


def list_devices() -> None:
    print("\n--- Available Audio Devices ---")
    for i, d in enumerate(sd.query_devices()):
        print(f"{i:>3}  in={d['max_input_channels']:<2} out={d['max_output_channels']:<2}  (rate={int(d['default_samplerate'])})  {d['name']}")
    print("--------------------------------\n")


def is_device_working(dev_id: int | str, is_input: bool) -> bool:
    """Check if an audio device can be opened successfully without crashing."""
    try:
        idx = int(dev_id) if str(dev_id).isdigit() else dev_id
        d = sd.query_devices(idx)
        rate = int(d['default_samplerate'])
        if is_input:
            if d['max_input_channels'] == 0:
                return False
            with sd.RawInputStream(device=idx, samplerate=rate, channels=CHANNELS, dtype="int16", callback=lambda a, b, c, d: None):
                pass
        else:
            if d['max_output_channels'] == 0:
                return False
            with sd.RawOutputStream(device=idx, samplerate=rate, channels=CHANNELS, dtype="int16"):
                pass
        return True
    except Exception:
        return False


def find_headset_and_audio_devices() -> tuple[int, int]:
    """Auto-detect the Bluetooth headset microphone and computer/headset audio output."""
    devices = sd.query_devices()
    in_idx, out_idx = None, None

    # Priority 1: Bluetooth Headset Mic (e.g. Airdopes 280 ANC, AirPods, Bluetooth Headset)
    for i, d in enumerate(devices):
        name = d['name'].lower()
        host = sd.query_hostapis(d['hostapi'])['name']
        if host in ['MME', 'Windows DirectSound', 'Windows WASAPI']:
            if d['max_input_channels'] > 0:
                if any(k in name for k in ['airdopes', 'headset', 'airpods', 'enco', 'bluetooth', 'hands-free']):
                    if is_device_working(i, True):
                        in_idx = i
                        break

    # Fallback input: Computer microphone array
    if in_idx is None:
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0 and 'microphone' in d['name'].lower() and is_device_working(i, True):
                in_idx = i
                break
    if in_idx is None:
        in_idx = sd.default.device[0]

    # Priority 2: Computer Sound / PC Speakers (Realtek Audio)
    for i, d in enumerate(devices):
        name = d['name'].lower()
        host = sd.query_hostapis(d['hostapi'])['name']
        if host in ['MME', 'Windows DirectSound', 'Windows WASAPI']:
            if d['max_output_channels'] > 0:
                if 'speakers' in name and 'realtek' in name and is_device_working(i, False):
                    out_idx = i
                    break

    # Fallback output: other speakers or default output
    if out_idx is None:
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0 and 'speakers' in d['name'].lower() and is_device_working(i, False):
                out_idx = i
                break

    if out_idx is None:
        out_idx = sd.default.device[1]

    return in_idx, out_idx


def resample_pcm16(raw_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
    """Fast linear audio resampling for 16-bit PCM (e.g. 8kHz phone telephony <-> 24kHz OpenAI)."""
    if in_rate == out_rate or not raw_bytes:
        return raw_bytes
    samples = np.frombuffer(raw_bytes, dtype=np.int16)
    num_out = int(len(samples) * out_rate / in_rate)
    x_old = np.linspace(0, len(samples), len(samples), endpoint=False)
    x_new = np.linspace(0, len(samples), num_out, endpoint=False)
    resampled = np.interp(x_new, x_old, samples).astype(np.int16)
    return resampled.tobytes()


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
    """Handles an active phone conversation session in Malayalam with the caller."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("Set OPENAI_API_KEY before running.")
        return

    # Validate devices can stream, or fallback smoothly
    if not is_device_working(input_device, True):
        print(f"  ℹ️ Device #{input_device} is in standby. Using active microphone (Device #1)...")
        input_device = 1
    if not is_device_working(output_device, False):
        print(f"  ℹ️ Device #{output_device} is in standby. Using active output (Device #3)...")
        output_device = 3

    in_dev_info = sd.query_devices(input_device)
    out_dev_info = sd.query_devices(output_device)
    in_rate = int(in_dev_info['default_samplerate'])
    out_rate = int(out_dev_info['default_samplerate'])
    in_block = int(in_rate * 0.02)   # 20ms block
    out_block = int(out_rate * 0.02) # 20ms block

    print(f"  Input: Device #{input_device} - {in_dev_info['name']} ({in_rate} Hz)")
    print(f"  Output: Device #{output_device} - {out_dev_info['name']} ({out_rate} Hz)")

    loop = asyncio.get_running_loop()
    mic_chunks: asyncio.Queue[bytes] = asyncio.Queue(maxsize=300)
    speaker_chunks: queue.Queue[bytes | None] = queue.Queue(maxsize=300)
    transcript: list[dict[str, str]] = []

    last_user_speech_time = [time.time()]
    conversation_active = [False]

    def push_mic_chunk(chunk: bytes):
        try:
            mic_chunks.put_nowait(chunk)
        except asyncio.QueueFull:
            try:
                mic_chunks.get_nowait()
                mic_chunks.put_nowait(chunk)
            except Exception:
                pass

    def on_input(indata, frames, time_info, status):
        raw = bytes(indata)
        rms = compute_rms(raw)
        if rms > WAKE_RMS_THRESHOLD:
            last_user_speech_time[0] = time.time()
        # Resample from device native rate to 24kHz for OpenAI Realtime
        pcm24k = resample_pcm16(raw, in_rate, OAI_RATE)
        try:
            loop.call_soon_threadsafe(push_mic_chunk, pcm24k)
        except RuntimeError:
            pass

    def play_worker():
        with sd.RawOutputStream(
            device=output_device, samplerate=out_rate, channels=CHANNELS, dtype="int16", blocksize=out_block
        ) as out:
            while True:
                chunk24k = speaker_chunks.get()
                if chunk24k is None:
                    return
                # Resample from 24kHz to device native rate for phone speaker/mic
                device_pcm = resample_pcm16(chunk24k, OAI_RATE, out_rate)
                out.write(device_pcm)

    playback = threading.Thread(target=play_worker, daemon=True)
    playback.start()

    headers = {"Authorization": f"Bearer {key}"}
    print(f"\n📞 Answering incoming call on phone bridge (English Mode)...")

    try:
        async with websockets.connect(URL, additional_headers=headers, ping_interval=20) as ws:
            # Configure OpenAI Realtime session in English
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "model": MODEL,
                    "instructions": (
                        "You are Call2Code, an AI answering a phone call from a business owner to create and launch their website. "
                        "Speak in clear, friendly, and professional English. "
                        "Greet the caller: 'Hello! I am Call2Code, your AI website builder. What is your business called, and what products or services do you offer?' "
                        "Listen carefully to their answer. Then ask one short, friendly follow-up question to learn about their target audience and key website features (like a contact form, testimonials, or services list). "
                        "When they finish, say: 'Great! I have all your requirements. I am generating your tailored website now with Kimi K3 and deploying it live to Vercel.' "
                        "Keep your responses concise and natural for a phone conversation."
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

            # Trigger opening AI greeting immediately in English
            await ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions": "Greet the caller warmly in English: 'Hello! I am Call2Code, your AI website builder. What is your business called, and what products or services do you offer?'"
                }
            }))
            print("🟢 Call answered! AI speaking in English to caller.")

            async def send_audio():
                with sd.RawInputStream(
                    device=input_device, samplerate=in_rate, channels=CHANNELS, dtype="int16", blocksize=in_block,
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
                        try:
                            speaker_chunks.put_nowait(base64.b64decode(event["delta"]))
                        except queue.Full:
                            pass

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
                """Monitors for call completion via ADB hangup or silence."""
                while True:
                    await asyncio.sleep(0.5)
                    call_state = get_adb_call_state()
                    if conversation_active[0] and call_state == 0:
                        print("\n📞 Caller hung up (Android telephony returned to idle).")
                        break
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


async def run_voice_agent(input_device: int | str, output_device: int | str) -> None:
    """Run interactive Call2Code voice session using Bluetooth headset mic & computer audio."""
    in_info = sd.query_devices(input_device)
    out_info = sd.query_devices(output_device)

    print("\n" + "="*65)
    print("🎧 CALL2CODE VOICE AGENT (PC SOUND + HEADSET MIC)")
    print(f"🎤 Mic:          Device #{input_device} - {in_info['name']}")
    print(f"🔊 PC Sound Out: Device #{output_device} - {out_info['name']}")
    print("="*65)
    print("🚀 Connecting to AI... Speak into your Bluetooth headset!")
    print("   (Audio will play out loud through your PC speakers)")
    print("="*65 + "\n")

    while True:
        await handle_call_session(input_device, output_device)
        print("\n" + "="*65)
        print("🎉 Conversation finished! Website generated & deployed live.")
        print("👉 Press [ENTER] in this window to start another build session (or Ctrl+C to exit)...")
        print("="*65)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, sys.stdin.readline)
        except Exception:
            await asyncio.sleep(2.0)


def main():
    parser = argparse.ArgumentParser(description="Call2Code Voice Agent (Bluetooth Headset & Computer Audio)")
    parser.add_argument("--list-devices", action="store_true", help="List audio input and output devices")
    parser.add_argument("--input", help="Audio input device index (Bluetooth headset mic)")
    parser.add_argument("--output", help="Audio output device index (Computer/Headset audio)")
    parser.add_argument("--speaker", action="store_true", help="Force output to computer speakers (Realtek Audio)")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    in_dev = args.input
    out_dev = args.output

    if in_dev is None or out_dev is None:
        auto_in, auto_out = find_headset_and_audio_devices()
        in_dev = in_dev or auto_in
        out_dev = out_dev or auto_out

    if args.speaker:
        # Force computer speakers
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0 and 'speakers' in d['name'].lower():
                out_dev = i
                break

    def parse_dev(val: int | str) -> int | str:
        return int(val) if str(val).isdigit() else val

    in_dev = parse_dev(in_dev)
    out_dev = parse_dev(out_dev)

    try:
        asyncio.run(run_voice_agent(in_dev, out_dev))
    except KeyboardInterrupt:
        print("\nVoice agent stopped by user.")


if __name__ == "__main__":
    main()
