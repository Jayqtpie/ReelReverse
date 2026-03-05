from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class FeaturePacket:
    transcript_quality: float
    scene_confidence: float
    ocr_confidence: float
    consistency: float
    cut_frequency: float
    speech_rate_wpm: int
    pattern_interrupts: int
    on_screen_text_density: float
    audio_spike: float
    first_3s_hook_density: float


def packet_from_seed(seed: str) -> FeaturePacket:
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16)
    return FeaturePacket(
        transcript_quality=0.45 + (h % 55) / 100,
        scene_confidence=0.4 + ((h >> 3) % 60) / 100,
        ocr_confidence=0.35 + ((h >> 6) % 60) / 100,
        consistency=0.5 + ((h >> 9) % 45) / 100,
        cut_frequency=0.8 + ((h >> 12) % 35) / 10,
        speech_rate_wpm=120 + ((h >> 15) % 120),
        pattern_interrupts=((h >> 18) % 8),
        on_screen_text_density=((h >> 21) % 90) / 100,
        audio_spike=((h >> 24) % 100) / 100,
        first_3s_hook_density=((h >> 27) % 100) / 100,
    )


def _packet_with_overrides(base: FeaturePacket, overrides: dict | None) -> FeaturePacket:
    if not overrides:
        return base
    data = base.__dict__.copy()
    for key, value in overrides.items():
        if key in data and value is not None:
            data[key] = value
    return FeaturePacket(**data)


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))


def confidence_score(packet: FeaturePacket) -> float:
    raw = (
        packet.transcript_quality * 0.40
        + packet.scene_confidence * 0.25
        + packet.ocr_confidence * 0.15
        + packet.consistency * 0.20
    )
    return round(max(0.0, min(1.0, raw)), 2)


def build_report(seed: str, metric_overrides: dict | None = None) -> dict:
    packet = _packet_with_overrides(packet_from_seed(seed), metric_overrides)
    confidence = confidence_score(packet)
    hook_score = _clamp(
        packet.first_3s_hook_density * 30
        + packet.on_screen_text_density * 20
        + packet.audio_spike * 20
        + min(packet.pattern_interrupts, 3) * 10
        + (10 if packet.speech_rate_wpm > 150 else 4)
    )
    pacing_score = _clamp(
        55
        + min(packet.cut_frequency * 5, 20)
        - abs(packet.speech_rate_wpm - 175) / 6
        + packet.pattern_interrupts * 3
    )

    pacing_timeline = []
    for i in range(0, 30, 5):
        density = packet.cut_frequency + (i / 30) - 1
        if density < 1.8:
            label = "slow"
        elif density > 3.8:
            label = "overloaded"
        else:
            label = "optimal"
        pacing_timeline.append(
            {
                "start_sec": i,
                "end_sec": i + 5,
                "label": label,
                "notes": f"cut_density={density:.1f}, speech_wpm={packet.speech_rate_wpm}",
            }
        )

    pattern = (
        "Problem->Promise"
        if packet.first_3s_hook_density > 0.65
        else "POV"
        if packet.speech_rate_wpm > 180
        else "Story-loop"
    )

    low_quality = confidence < 0.55
    warning_reason = "Low transcript/vision quality detected."
    hook_reasons = [
        "Strong opening contrast signal.",
        "Early spoken novelty cue.",
        "Visible text support in first seconds.",
    ]
    if low_quality:
        hook_reasons = [warning_reason, "Scoring weighted toward audio/scene priors."]

    return {
        "hook_score": hook_score,
        "pacing_score": pacing_score,
        "confidence": confidence,
        "hook_analysis": {
            "score": hook_score,
            "verdict": "strong" if hook_score >= 70 else "average" if hook_score >= 45 else "weak",
            "reasons": hook_reasons,
        },
        "pacing_timeline": pacing_timeline,
        "caption_formula": {
            "pattern": pattern,
            "slots": {
                "audience": "Creators trying to improve short-form retention",
                "pain": "views drop after first 3-5 seconds",
                "outcome": "higher watch-through by tighter pacing",
                "curiosity_gap": "one uncommon editing switch",
                "cta": "comment your niche for a tailored version",
            },
        },
        "remake_template": {
            "anti_plagiarism_notice": "Use structural patterns only. Rewrite in your own voice.",
            "sections": [
                {"name": "Hook (0-3s)", "prompt": "Open with a bold claim tied to a viewer pain point."},
                {"name": "Context", "prompt": "Name the situation in one sentence."},
                {"name": "Value Beat 1", "prompt": "Show one concrete tactic quickly."},
                {"name": "Value Beat 2", "prompt": "Add a surprising contrast or interrupt."},
                {"name": "Proof", "prompt": "Give an observable result or example."},
                {"name": "CTA", "prompt": "Invite a specific next action without copying source phrasing."},
            ],
        },
    }
