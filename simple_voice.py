"""Simple English Call2Code voice prototype for Windows, macOS, and Linux.

Run `python simple_voice.py --list-devices` to see microphone/speaker IDs.
Run `python simple_voice.py` to talk, then press Enter to build the website.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import queue
import sys
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

import numpy as np
import sounddevice as sd
import websockets


ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL = os.getenv("OPENAI_PYTHON_REALTIME_MODEL", "gpt-realtime-2.1-mini")
RATE = 24_000
CHANNELS = 1
BLOCK_MS = 20
INSTRUCTIONS = (
    "You are Call2Code, a friendly AI website builder. You are an AI; say so clearly. "
    "Speak English only. Begin with a short, friendly English greeting. If the caller "
    "speaks another language, politely ask them to continue in English. Ask one short question at a time about the business "
    "name, products or services, audience, preferred style, pages, contact details, and "
    "website goal. Keep replies brief and conversational."
)


def load_dotenv() -> None:
    """Load simple KEY=value entries from the project .env without printing them."""
    path = os.path.join(ROOT, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8", errors="replace") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(name.strip(), value)


def resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or samples.size == 0:
        return samples.astype(np.int16, copy=False)
    count = max(1, round(samples.size * target_rate / source_rate))
    old_x = np.arange(samples.size)
    new_x = np.linspace(0, samples.size - 1, count)
    return np.interp(new_x, old_x, samples).astype(np.int16)


def parse_device(value: str | None) -> int | None:
    return int(value) if value is not None and value.isdigit() else None


def list_devices() -> None:
    print("Audio devices (use the ID with --input or --output):")
    for index, device in enumerate(sd.query_devices()):
        print(
            f"{index:>3}  in={device['max_input_channels']:<2} "
            f"out={device['max_output_channels']:<2}  {device['name']}"
        )


async def deploy(transcript: list[dict[str, str]]) -> None:
    if not any(item["role"] == "user" for item in transcript):
        print("No caller speech was captured, so there is no website brief to build.")
        return

    base_url = os.getenv("CALL2CODE_SERVER_URL", "http://localhost:3000").rstrip("/")
    payload = json.dumps({"transcript": transcript}).encode("utf-8")
    create_request = urllib.request.Request(
        f"{base_url}/api/projects",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(create_request, timeout=30) as response:
            project = json.loads(response.read().decode("utf-8"))
        project_id = project.get("id")
        if not project_id:
            raise RuntimeError("The Call2Code server did not return a project ID.")

        print("Building and deploying your website…")
        build_request = urllib.request.Request(
            f"{base_url}/api/projects/{quote(project_id)}/generate",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(build_request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("deploymentUrl"):
            raise RuntimeError(result.get("error", "Website deployment did not return a link."))
        print(f"Your website is live: {result['deploymentUrl']}")
    except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError) as error:
        print(f"Could not build the website: {error}")
        print("Make sure the Call2Code server is running and its Vercel settings are configured.")


async def run(input_device: int | None, output_device: int | None) -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to the project .env file.")

    chosen_input, chosen_output = sd.default.device
    input_device = input_device if input_device is not None else chosen_input
    output_device = output_device if output_device is not None else chosen_output
    input_info = sd.query_devices(input_device, "input")
    output_info = sd.query_devices(output_device, "output")
    input_rate = int(input_info["default_samplerate"])
    output_rate = int(output_info["default_samplerate"])

    audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
    playback_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=100)
    transcript: list[dict[str, str]] = []
    loop = asyncio.get_running_loop()

    def enqueue_audio(pcm: bytes) -> None:
        if audio_queue.full():
            try:
                audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            audio_queue.put_nowait(pcm)
        except asyncio.QueueFull:
            pass

    def microphone_callback(indata: np.ndarray, _frames: int, _time_info: object, status: sd.CallbackFlags) -> None:
        if status:
            print(f"Microphone notice: {status}", file=sys.stderr)
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata
        pcm = resample(np.clip(mono, -1, 1) * 32767, input_rate, RATE)
        loop.call_soon_threadsafe(enqueue_audio, pcm.tobytes())

    def speaker_worker() -> None:
        try:
            with sd.RawOutputStream(
                device=output_device,
                samplerate=output_rate,
                channels=CHANNELS,
                dtype="int16",
            ) as speaker:
                while True:
                    chunk = playback_queue.get()
                    if chunk is None:
                        break
                    samples = np.frombuffer(chunk, dtype=np.int16)
                    speaker.write(resample(samples, RATE, output_rate).tobytes())
        except Exception as error:
            print(f"Speaker error: {error}", file=sys.stderr)

    speaker_thread = threading.Thread(target=speaker_worker, daemon=True)
    speaker_thread.start()
    url = f"wss://api.openai.com/v1/realtime?model={quote(MODEL)}"
    headers = {"Authorization": f"Bearer {api_key}"}

    print(f"Microphone: {input_info['name']}")
    print(f"Speaker:    {output_info['name']}")
    print("Connecting to the English voice assistant…")
    print("Use headphones to prevent speaker audio feeding back into the microphone.")

    try:
        async with websockets.connect(url, additional_headers=headers, ping_interval=20) as socket:
            await socket.send(json.dumps({
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "model": MODEL,
                    "output_modalities": ["audio"],
                    "instructions": INSTRUCTIONS,
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": RATE},
                            "noise_reduction": {"type": "near_field"},
                            "transcription": {"model": "gpt-realtime-whisper", "language": "en"},
                            "turn_detection": {"type": "semantic_vad"},
                        },
                        "output": {
                            "format": {"type": "audio/pcm", "rate": RATE},
                            "voice": "marin",
                        },
                    },
                },
            }))
            await socket.send(json.dumps({"type": "response.create"}))

            async def send_microphone() -> None:
                with sd.InputStream(
                    device=input_device,
                    samplerate=input_rate,
                    channels=int(input_info["max_input_channels"] > 1) + 1,
                    dtype="float32",
                    blocksize=max(1, round(input_rate * BLOCK_MS / 1000)),
                    callback=microphone_callback,
                ):
                    print("Listening. Speak naturally; press Enter here to finish and build the site.")
                    while True:
                        chunk = await audio_queue.get()
                        await socket.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(chunk).decode("ascii"),
                        }))

            async def receive_ai() -> None:
                async for raw_message in socket:
                    event = json.loads(raw_message)
                    kind = event.get("type", "")
                    if kind == "conversation.item.input_audio_transcription.completed":
                        text = event.get("transcript", "").strip()
                        if text:
                            transcript.append({"role": "user", "text": text})
                            print(f"\nYou: {text}")
                    elif kind == "response.output_audio.delta":
                        try:
                            playback_queue.put_nowait(base64.b64decode(event["delta"]))
                        except queue.Full:
                            pass
                    elif kind == "response.output_audio_transcript.done":
                        text = event.get("transcript", "").strip()
                        if text:
                            transcript.append({"role": "assistant", "text": text})
                            print(f"AI: {text}")
                    elif kind == "error":
                        detail = event.get("error", {}).get("message", "Unknown Realtime API error")
                        print(f"\nOpenAI error: {detail}", file=sys.stderr)

            mic_task = asyncio.create_task(send_microphone())
            ai_task = asyncio.create_task(receive_ai())
            enter_task = asyncio.create_task(asyncio.to_thread(input, "\nPress Enter to finish: "))
            done, pending = await asyncio.wait(
                {mic_task, ai_task, enter_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                if task is not enter_task:
                    task.result()
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
    finally:
        try:
            playback_queue.put_nowait(None)
        except queue.Full:
            pass
        speaker_thread.join(timeout=2)

    await deploy(transcript)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple English Call2Code voice prototype")
    parser.add_argument("--list-devices", action="store_true", help="Show available microphones and speakers")
    parser.add_argument("--input", help="Microphone device ID")
    parser.add_argument("--output", help="Speaker device ID")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    try:
        asyncio.run(run(parse_device(args.input), parse_device(args.output)))
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as error:
        print(f"Could not start voice assistant: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
