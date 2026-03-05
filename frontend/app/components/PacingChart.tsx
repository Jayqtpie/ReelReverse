"use client";

type TimelinePoint = {
  start_sec: number;
  end_sec: number;
  label: string;
  notes: string;
  cut_frequency?: number;
  speech_rate_wpm?: number;
  audio_spike?: number;
  pattern_interrupts?: number;
};

type Props = {
  points: TimelinePoint[];
};

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

export default function PacingChart({ points }: Props) {
  if (!points.length) {
    return <p>No pacing timeline available.</p>;
  }

  const w = 680;
  const h = 220;
  const left = 50;
  const right = 20;
  const top = 20;
  const bottom = 35;
  const innerW = w - left - right;
  const innerH = h - top - bottom;
  const stepX = points.length > 1 ? innerW / (points.length - 1) : innerW;

  const cuts = points.map((p) => p.cut_frequency ?? 0);
  const speech = points.map((p) => p.speech_rate_wpm ?? 0);
  const spike = points.map((p) => p.audio_spike ?? 0);

  const maxCut = Math.max(5, ...cuts);
  const maxSpeech = Math.max(260, ...speech);

  const cutPath = points
    .map((p, i) => {
      const x = left + i * stepX;
      const y = top + innerH - (clamp(p.cut_frequency ?? 0, 0, maxCut) / maxCut) * innerH;
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  const speechPath = points
    .map((p, i) => {
      const x = left + i * stepX;
      const y = top + innerH - (clamp(p.speech_rate_wpm ?? 0, 0, maxSpeech) / maxSpeech) * innerH;
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Pacing metrics over timeline" style={{ width: "100%" }}>
        <rect x={left} y={top} width={innerW} height={innerH} fill="#f8faf7" stroke="#d5dfd1" />
        {points.map((p, i) => {
          const x = left + i * stepX;
          const barH = (clamp(p.audio_spike ?? 0, 0, 1) / 1) * innerH;
          return (
            <rect
              key={`${p.start_sec}-${p.end_sec}`}
              x={x - 9}
              y={top + innerH - barH}
              width={18}
              height={barH}
              fill="rgba(47, 125, 50, 0.2)"
            />
          );
        })}
        <path d={cutPath} fill="none" stroke="#2f7d32" strokeWidth="2.5" />
        <path d={speechPath} fill="none" stroke="#0f4a87" strokeWidth="2.5" />
        {points.map((p, i) => {
          const x = left + i * stepX;
          return (
            <text key={`tick-${p.start_sec}`} x={x} y={h - 10} fontSize="10" textAnchor="middle" fill="#5b6b5a">
              {p.start_sec}s
            </text>
          );
        })}
      </svg>
      <p style={{ fontSize: 13, marginTop: 8 }}>
        <strong>Legend:</strong> green line = cut frequency, blue line = speech rate, green bars = audio spike.
      </p>
    </div>
  );
}
