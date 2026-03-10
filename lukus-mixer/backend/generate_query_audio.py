"""
Banquet 레퍼런스 쿼리 오디오 생성기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
각 악기의 특성을 모사한 합성 오디오를 생성하여
Banquet 쿼리 파일로 사용한다.

※ 실제 악기 녹음 파일로 교체하면 분리 품질이 향상됩니다.
   권장: Freesound.org (CC0) 또는 MoisesDB 레퍼런스
   출처: https://freesound.org

생성 대상: 바이올린(현악기), 트럼펫(금관), 플루트(목관), 신디사이저

실행:
    python generate_query_audio.py
"""

import numpy as np
import os

SAMPLE_RATE = 44100
DURATION = 10.0
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "banquet_queries")


def _save_wav(filepath: str, audio: np.ndarray, sr: int = SAMPLE_RATE):
    """numpy 배열을 WAV 파일로 저장 (16-bit PCM)"""
    import struct
    import wave

    audio = np.clip(audio, -1.0, 1.0)
    int16_data = (audio * 32767).astype(np.int16)

    n_channels = 1 if audio.ndim == 1 else audio.shape[0]
    if audio.ndim == 2:
        int16_data = int16_data.T.flatten()

    with wave.open(filepath, "w") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16_data.tobytes())


def _generate_violin(duration: float = DURATION, sr: int = SAMPLE_RATE) -> np.ndarray:
    """바이올린 근사 — 풍부한 홀수 배음 + 비브라토 + 보잉 엔벨로프

    참고: 바이올린의 음색 특성
    - 강한 홀수 배음 (1, 3, 5, 7, 9차)
    - 약한 짝수 배음
    - 비브라토 (5-7Hz, ±20 cent 정도)
    """
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    f0 = 440.0
    vibrato_rate = 5.5
    vibrato_depth = 6.0
    vibrato = vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
    freq = f0 + vibrato

    phase = 2 * np.pi * np.cumsum(freq) / sr

    harmonics = [
        (1, 1.0),
        (2, 0.35),
        (3, 0.65),
        (4, 0.2),
        (5, 0.5),
        (7, 0.25),
        (9, 0.12),
    ]

    audio = np.zeros_like(t)
    for n, amp in harmonics:
        audio += amp * np.sin(n * phase)

    attack = np.minimum(t / 0.15, 1.0)
    decay = np.minimum((duration - t) / 0.1, 1.0)
    envelope = attack * decay

    audio = audio * envelope
    audio = audio / (np.max(np.abs(audio)) + 1e-8) * 0.8
    return audio


def _generate_trumpet(duration: float = DURATION, sr: int = SAMPLE_RATE) -> np.ndarray:
    """트럼펫 근사 — 강한 짝수/홀수 배음 + 밝은 스펙트럼

    참고: 트럼펫(금관악기) 음색 특성
    - 전 배음 영역에서 풍부한 에너지
    - 특히 고차 배음(8~12차)까지 강한 에너지
    - 날카로운 어택
    """
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    f0 = 466.16  # Bb4
    vibrato = 3.0 * np.sin(2 * np.pi * 5.0 * t) * np.minimum(t / 1.0, 1.0)
    freq = f0 + vibrato
    phase = 2 * np.pi * np.cumsum(freq) / sr

    harmonics = [
        (1, 1.0),
        (2, 0.8),
        (3, 0.7),
        (4, 0.55),
        (5, 0.45),
        (6, 0.35),
        (7, 0.25),
        (8, 0.2),
        (10, 0.1),
    ]

    audio = np.zeros_like(t)
    for n, amp in harmonics:
        audio += amp * np.sin(n * phase)

    attack = np.minimum(t / 0.04, 1.0)
    sustain = np.ones_like(t)
    release = np.minimum((duration - t) / 0.08, 1.0)
    envelope = np.minimum(attack, sustain) * release

    audio = audio * envelope
    audio = audio / (np.max(np.abs(audio)) + 1e-8) * 0.8
    return audio


def _generate_flute(duration: float = DURATION, sr: int = SAMPLE_RATE) -> np.ndarray:
    """플루트 근사 — 약한 배음 + 숨 노이즈 성분

    참고: 플루트(목관악기) 음색 특성
    - 기음이 지배적, 배음이 약함
    - 공기 노이즈 (breath noise) 성분 혼합
    - 부드러운 어택
    """
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    f0 = 523.25  # C5
    vibrato = 4.0 * np.sin(2 * np.pi * 5.0 * t) * np.minimum(t / 0.5, 1.0)
    freq = f0 + vibrato
    phase = 2 * np.pi * np.cumsum(freq) / sr

    harmonics = [(1, 1.0), (2, 0.25), (3, 0.1), (4, 0.05)]

    audio = np.zeros_like(t)
    for n, amp in harmonics:
        audio += amp * np.sin(n * phase)

    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.03, len(t))

    from scipy.signal import butter, lfilter
    b, a = butter(4, [800 / (sr / 2), 6000 / (sr / 2)], btype="band")
    noise = lfilter(b, a, noise)

    audio = audio + noise

    attack = np.minimum(t / 0.25, 1.0)
    release = np.minimum((duration - t) / 0.15, 1.0)
    envelope = attack * release

    audio = audio * envelope
    audio = audio / (np.max(np.abs(audio)) + 1e-8) * 0.8
    return audio


def _generate_synth(duration: float = DURATION, sr: int = SAMPLE_RATE) -> np.ndarray:
    """신디사이저 근사 — 톱니파 + 저역통과필터 + LFO 모듈레이션

    참고: 아날로그 신디사이저 음색 특성
    - 톱니파(sawtooth) 기반의 풍부한 배음
    - 저역통과 필터(LPF) 스윕으로 밝기 변화
    - LFO 기반 트레몰로/필터 모듈레이션
    """
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    f0 = 261.63  # C4
    phase = 2 * np.pi * f0 * t
    sawtooth = 2.0 * (phase / (2 * np.pi) - np.floor(phase / (2 * np.pi) + 0.5))

    lfo = 0.3 * np.sin(2 * np.pi * 0.5 * t)
    audio = sawtooth * (0.7 + lfo)

    from scipy.signal import butter, lfilter
    cutoff = 3000
    b, a = butter(4, cutoff / (sr / 2), btype="low")
    audio = lfilter(b, a, audio)

    attack = np.minimum(t / 0.01, 1.0)
    release = np.minimum((duration - t) / 0.3, 1.0)
    envelope = attack * release

    audio = audio * envelope
    audio = audio / (np.max(np.abs(audio)) + 1e-8) * 0.8
    return audio


def generate_all():
    """모든 레퍼런스 쿼리 오디오를 생성"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generators = {
        "strings_query.wav": (_generate_violin, "바이올린 (현악기 쿼리)"),
        "brass_query.wav": (_generate_trumpet, "트럼펫 (금관악기 쿼리)"),
        "woodwinds_query.wav": (_generate_flute, "플루트 (목관악기 쿼리)"),
        "synthesizer_query.wav": (_generate_synth, "신디사이저 쿼리"),
    }

    for filename, (gen_fn, desc) in generators.items():
        filepath = os.path.join(OUTPUT_DIR, filename)
        audio = gen_fn()
        _save_wav(filepath, audio)
        print(f"  ✅ {desc}: {filepath} ({audio.shape[0]/SAMPLE_RATE:.1f}s)")

    readme_path = os.path.join(OUTPUT_DIR, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            "# Banquet 레퍼런스 쿼리 오디오\n\n"
            "이 폴더의 WAV 파일은 Banquet 쿼리 기반 분리에 사용됩니다.\n\n"
            "## 파일 목록\n"
            "- `strings_query.wav` — 현악기 (바이올린) 레퍼런스\n"
            "- `brass_query.wav` — 금관악기 (트럼펫) 레퍼런스\n"
            "- `woodwinds_query.wav` — 목관악기 (플루트) 레퍼런스\n"
            "- `synthesizer_query.wav` — 신디사이저 레퍼런스\n\n"
            "## 품질 향상 팁\n"
            "합성 오디오 대신 실제 악기 녹음을 사용하면 분리 품질이 향상됩니다.\n"
            "- Freesound.org (CC0 라이선스): https://freesound.org\n"
            "- MoisesDB 레퍼런스: https://github.com/moises-ai/moises-db\n\n"
            "10초 길이의 모노/스테레오 WAV 파일을 같은 이름으로 교체하세요.\n"
        )

    print(f"\n모든 쿼리 오디오 생성 완료: {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_all()
