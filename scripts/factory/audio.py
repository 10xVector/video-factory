import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import re
import json
import base64
import subprocess
from typing import List, Tuple, Dict, Optional

OG_TIKTOK_VOICE = "en_us_001"

VOICE_PRESETS = {
    "tiktok-jessie": "en_us_001",
    "jessie": "en_us_001",
    "tiktok-female": "en_us_001",
    "tiktok-male": "en_us_006",
    "tiktok-narrator": "en_male_narration",
    "tiktok-uk": "en_uk_001",
    "tiktok-au": "en_au_001",
    "rocket": "en_us_rocket",
    "default": "en_us_001",
    "og": "en_us_001",
}


def resolve_voice_id(voice: str) -> str:
    if not voice:
        return OG_TIKTOK_VOICE
    v = VOICE_PRESETS.get(voice.strip().lower(), voice.strip())
    if not v.startswith("en_"):
        return OG_TIKTOK_VOICE
    return v


def generate_tiktok_tts(text: str, voice: str = OG_TIKTOK_VOICE, out_path: str = "", tempo: float = 1.18) -> float:
    """
    Generates audio using the TikTok Text-To-Speech endpoint.
    Defaults to `en_us_001` (Jessie) with a fallback to macOS `say` if offline.
    """
    voice_id = resolve_voice_id(voice)

    import time
    max_retries = 3
    last_err = None

    for attempt in range(max_retries):
        cmd = [
            "curl", "-s", "-S", "-L", "-X", "POST",
            "https://tiktok-tts.weilnet.workers.dev/api/generation",
            "-H", "Content-Type: application/json",
            "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "-d", json.dumps({"text": text, "voice": voice_id}),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            try:
                data = json.loads(res.stdout)
                if data.get("success") and "data" in data:
                    raw_path = out_path + ".raw.mp3"
                    with open(raw_path, "wb") as f:
                        f.write(base64.b64decode(data["data"]))
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", raw_path,
                            "-filter:a", f"atempo={tempo}",
                            "-c:a", "libmp3lame", "-q:a", "2",
                            out_path,
                        ],
                        capture_output=True,
                        check=True,
                    )
                    if os.path.exists(raw_path):
                        os.remove(raw_path)
                    probe = subprocess.run(
                        [
                            "ffprobe", "-i", out_path,
                            "-show_entries", "format=duration",
                            "-v", "quiet", "-of", "csv=p=0",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    return float(probe.stdout.strip())
                else:
                    last_err = RuntimeError(f"TikTok TTS error: {data.get('error')}")
            except Exception as e:
                last_err = e
        else:
            last_err = RuntimeError(f"curl failed: {res.stderr}")
        time.sleep(1.0 * (attempt + 1))

    raise RuntimeError(f"TikTok TTS failed after {max_retries} attempts: {last_err}")


def math_ceil_duration(sec: float) -> float:
    return round(sec, 1)


def _ensure_pop_sfx(work_dir: str, pop_sfx_path: str = "/System/Library/Sounds/Pop.aiff") -> str:
    """Returns a valid transition pop audio file path, generating a subtle sine pop if not on macOS."""
    if os.path.exists(pop_sfx_path):
        return pop_sfx_path
    fallback_pop = os.path.join(work_dir, "fallback_pop.wav")
    if not os.path.exists(fallback_pop):
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "sine=frequency=520:duration=0.05",
                "-af", "afade=t=out:st=0.01:d=0.04,volume=0.3",
                fallback_pop,
            ],
            capture_output=True,
            check=True,
        )
    return fallback_pop


def build_audio_track(
    vo_texts: List[str],
    voice: str,
    work_dir: str,
    pop_sfx_path: str = "/System/Library/Sounds/Pop.aiff",
    pitch_shift: float = 0.0,
    speed: float = 1.0,
) -> Dict:
    """
    Generates TTS for the 4 scenes of the App Template (`screen_walkthrough` or `before_after_slider`):
      Scene 1: Hook
      Scene 2: Reveal / Screen 2 Transition
      Scene 3: Breakdown / Feature Sheet
      Scene 4: Outro & CTA
    """
    os.makedirs(work_dir, exist_ok=True)
    pop_sfx = _ensure_pop_sfx(work_dir, pop_sfx_path)
    vo_files = []
    vo_durations = []

    clean_voice = resolve_voice_id(voice)
    print(f"🎙️ Generating 4-scene voiceovers with TikTok TTS ({clean_voice})...")

    for idx, text in enumerate(vo_texts):
        vo_path = os.path.join(work_dir, f"vo_{idx+1}.mp3")
        dur = generate_tiktok_tts(text, clean_voice, vo_path)
        vo_files.append(vo_path)
        vo_durations.append(dur)
        print(f"   Scene {idx+1} audio: {dur:.2f}s | \"{text[:50]}...\"")

    s1_start = 0.0
    s1_vo_start = 0.12
    s1_end = s1_vo_start + vo_durations[0] + 0.10

    s2_start = s1_end
    s2_vo_start = s2_start + 0.12
    s2_end = s2_vo_start + vo_durations[1] + 0.12

    s3_start = s2_end
    s3_vo_start = s3_start + 0.12
    s3_end = s3_vo_start + vo_durations[2] + 0.18

    s4_start = s3_end
    s4_vo_start = s4_start + 0.18
    s4_end = s4_vo_start + vo_durations[3] + 0.35

    total_seconds = math_ceil_duration(s4_end)
    master_aac = os.path.join(work_dir, "master_audio.aac")
    ms = lambda sec: int(sec * 1000)

    filter_complex = (
        f"[0:a]adelay={ms(s1_vo_start)}|{ms(s1_vo_start)}[a0]; "
        f"[4:a]adelay={ms(s1_end)}|{ms(s1_end)}[pop1]; "
        f"[1:a]adelay={ms(s2_vo_start)}|{ms(s2_vo_start)}[a1]; "
        f"[4:a]adelay={ms(s2_end)}|{ms(s2_end)}[pop2]; "
        f"[2:a]adelay={ms(s3_vo_start)}|{ms(s3_vo_start)}[a2]; "
        f"[3:a]adelay={ms(s4_vo_start)}|{ms(s4_vo_start)}[a3]; "
        f"[a0][pop1][a1][pop2][a2][a3]amix=inputs=6:dropout_transition=0,dynaudnorm=f=75:g=15,volume=1.8[aout]"
    )

    mix_cmd = [
        "ffmpeg", "-y",
        "-i", vo_files[0],
        "-i", vo_files[1],
        "-i", vo_files[2],
        "-i", vo_files[3],
        "-i", pop_sfx,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(total_seconds),
        master_aac,
    ]
    subprocess.run(mix_cmd, capture_output=True, check=True)
    print(f"🎵 Master audio muxed: {total_seconds:.2f}s total duration.")

    return {
        "master_audio_path": master_aac,
        "total_seconds": total_seconds,
        "scenes": [
            {"name": "hook", "start": s1_start, "end": s1_end},
            {"name": "reveal", "start": s2_start, "end": s2_end},
            {"name": "breakdown", "start": s3_start, "end": s3_end},
            {"name": "outro", "start": s4_start, "end": s4_end},
        ],
    }


def build_native_audio_track(
    vo_texts: List[str],
    voice: str,
    work_dir: str,
    pop_sfx_path: str = "/System/Library/Sounds/Pop.aiff",
    pitch_shift: float = 0.0,
    speed: float = 1.0,
) -> Dict:
    """
    Builds a 3-phase audio track for `side_by_side_proof` / `native_loop` formats.
    """
    os.makedirs(work_dir, exist_ok=True)
    pop_sfx = _ensure_pop_sfx(work_dir, pop_sfx_path)
    vo_files = []
    vo_durations = []

    clean_voice = resolve_voice_id(voice)
    print(f"🎙️ Generating 3-phase audio track with TikTok TTS ({clean_voice})...")

    for idx, text in enumerate(vo_texts):
        vo_path = os.path.join(work_dir, f"native_vo_{idx+1}.mp3")
        dur = generate_tiktok_tts(text, clean_voice, vo_path)
        vo_files.append(vo_path)
        vo_durations.append(dur)
        print(f"   Phase {idx+1} audio: {dur:.2f}s | \"{text[:50]}...\"")

    p1_start = 0.0
    p1_vo_start = 0.15
    p1_end = p1_vo_start + vo_durations[0] + 0.15

    p2_start = p1_end
    p2_vo_start = p2_start + 0.15
    p2_end = p2_vo_start + (vo_durations[1] if len(vo_durations) > 1 else 0.0) + 0.20

    p3_start = p2_end
    p3_vo_start = p3_start + 0.15
    p3_end = p3_vo_start + (vo_durations[2] if len(vo_durations) > 2 else 0.0) + 0.45

    total_seconds = math_ceil_duration(p3_end)
    master_aac = os.path.join(work_dir, "native_master_audio.aac")
    ms = lambda sec: int(sec * 1000)

    filter_complex = (
        f"[0:a]adelay={ms(p1_vo_start)}|{ms(p1_vo_start)}[a0]; "
        f"[3:a]adelay={ms(p2_start)}|{ms(p2_start)}[pop1]; "
        f"[1:a]adelay={ms(p2_vo_start)}|{ms(p2_vo_start)}[a1]; "
        f"[3:a]adelay={ms(p3_start)}|{ms(p3_start)}[pop2]; "
        f"[2:a]adelay={ms(p3_vo_start)}|{ms(p3_vo_start)}[a2]; "
        f"[a0][pop1][a1][pop2][a2]amix=inputs=5:dropout_transition=0,dynaudnorm=f=75:g=15,volume=1.8[aout]"
    )

    mix_cmd = [
        "ffmpeg", "-y",
        "-i", vo_files[0],
        "-i", vo_files[1] if len(vo_files) > 1 else vo_files[0],
        "-i", vo_files[2] if len(vo_files) > 2 else vo_files[0],
        "-i", pop_sfx,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(total_seconds),
        master_aac,
    ]
    subprocess.run(mix_cmd, capture_output=True, check=True)
    print(f"🎵 Native master audio muxed: {total_seconds:.2f}s total duration.")

    return {
        "master_audio_path": master_aac,
        "total_seconds": total_seconds,
        "phases": [
            {"name": "hook", "start": p1_start, "end": p1_end},
            {"name": "proof", "start": p2_start, "end": p2_end},
            {"name": "takeaway", "start": p3_start, "end": p3_end},
        ],
        "scenes": [
            {"name": "hook", "start": p1_start, "end": p1_end, "establish_end": p1_end},
            {"name": "reveal", "start": p2_start, "end": p2_end},
            {"name": "breakdown", "start": p2_start, "end": p2_end},
            {"name": "outro", "start": p3_start, "end": p3_end},
        ],
    }
