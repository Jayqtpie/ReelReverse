"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import PacingChart from "./components/PacingChart";

type JobStatus = {
  job_id: string;
  state: string;
  progress: number;
  stage: string;
  error_code?: string | null;
};

type ReportPayload = {
  job_id: string;
  hook_analysis: { score: number; verdict: string; reasons: string[] };
  pacing_timeline: {
    start_sec: number;
    end_sec: number;
    label: string;
    notes: string;
    cut_frequency?: number;
    speech_rate_wpm?: number;
    audio_spike?: number;
    pattern_interrupts?: number;
  }[];
  caption_formula: { pattern: string; slots: Record<string, string> };
  remake_template: { anti_plagiarism_notice: string; sections: { name: string; prompt: string }[] };
  artifacts: {
    transcript_source: string;
    transcript_quality: number;
    transcript_word_count: number;
    feature_source_mode: string;
    scene_quality: number;
    cut_frequency: number;
    audio_spike: number;
  };
  confidence: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [email, setEmail] = useState("creator@example.com");
  const [sourceType, setSourceType] = useState<"url" | "upload">("url");
  const [sourceUrl, setSourceUrl] = useState("https://youtu.be/dQw4w9WgXcQ");
  const [fileKey, setFileKey] = useState("uploads/sample.mp4");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState("");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [report, setReport] = useState<ReportPayload | null>(null);
  const [history, setHistory] = useState<{ job_id: string; state: string; confidence?: number | null }[]>([]);
  const [usage, setUsage] = useState<{ jobs_used: number; jobs_limit: number; plan: string } | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [exportJsonUrl, setExportJsonUrl] = useState("");
  const [exportPdfUrl, setExportPdfUrl] = useState("");
  const [isExporting, setIsExporting] = useState<"" | "json" | "pdf">("");

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      "x-user-email": email,
    }),
    [email],
  );

  async function submitJob(e: FormEvent) {
    e.preventDefault();
    setError("");
    setUploadState("");
    setReport(null);
    setExportJsonUrl("");
    setExportPdfUrl("");
    setIsSubmitting(true);
    try {
      let payload:
        | { source_type: "url"; source_url: string; confirm_rights: boolean }
        | { source_type: "upload"; file_key: string; duration_sec: number; confirm_rights: boolean };

      if (sourceType === "url") {
        payload = { source_type: "url", source_url: sourceUrl, confirm_rights: true };
      } else {
        const resolvedFileKey = selectedFile ? await uploadFile(selectedFile) : fileKey;
        if (!resolvedFileKey) throw new Error("upload_missing_file");
        payload = { source_type: "upload", file_key: resolvedFileKey, duration_sec: 60, confirm_rights: true };
      }

      const res = await fetch(`${API_BASE}/v1/jobs`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`submit_failed:${res.status}`);
      const data = await res.json();
      setJobId(data.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "submit_failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function requestExport(format: "json" | "pdf") {
    if (!jobId) return;
    setIsExporting(format);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/v1/reports/${jobId}/export`, {
        method: "POST",
        headers,
        body: JSON.stringify({ format }),
      });
      if (!res.ok) throw new Error(`export_failed:${res.status}`);
      const data = await res.json();
      const fullUrl = `${API_BASE}${data.download_url}`;
      if (format === "json") {
        setExportJsonUrl(fullUrl);
      } else {
        setExportPdfUrl(fullUrl);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "export_failed");
    } finally {
      setIsExporting("");
    }
  }

  async function uploadFile(file: File): Promise<string> {
    setUploadState("Requesting upload URL...");
    const presign = await fetch(`${API_BASE}/v1/uploads/presign`, {
      method: "POST",
      headers,
      body: JSON.stringify({ filename: file.name }),
    });
    if (!presign.ok) throw new Error(`upload_presign_failed:${presign.status}`);
    const presignJson = await presign.json();
    const uploadUrl = `${API_BASE}${presignJson.upload_url}`;
    const key = presignJson.file_key as string;

    setUploadState("Uploading media...");
    const uploadRes = await fetch(uploadUrl, {
      method: "PUT",
      headers: {
        "x-user-email": email,
        "Content-Type": "application/octet-stream",
      },
      body: file,
    });
    if (!uploadRes.ok) throw new Error(`upload_put_failed:${uploadRes.status}`);
    setFileKey(key);
    setUploadState("Upload complete.");
    return key;
  }

  useEffect(() => {
    if (!jobId) return;
    const timer = setInterval(async () => {
      const res = await fetch(`${API_BASE}/v1/jobs/${jobId}`, { headers });
      if (!res.ok) return;
      const data = (await res.json()) as JobStatus;
      setStatus(data);
      if (data.state === "done") {
        clearInterval(timer);
        const reportRes = await fetch(`${API_BASE}/v1/reports/${jobId}`, { headers });
        if (reportRes.ok) setReport((await reportRes.json()) as ReportPayload);
      }
    }, 1600);
    return () => clearInterval(timer);
  }, [jobId, headers]);

  async function refreshSidebarData() {
    const [historyRes, usageRes] = await Promise.all([
      fetch(`${API_BASE}/v1/reports`, { headers }),
      fetch(`${API_BASE}/v1/usage`, { headers }),
    ]);
    if (historyRes.ok) {
      const data = await historyRes.json();
      setHistory(data.items ?? []);
    }
    if (usageRes.ok) {
      setUsage(await usageRes.json());
    }
  }

  useEffect(() => {
    void refreshSidebarData();
  }, [headers]);

  return (
    <main>
      <h1>Reel Reverse-Engineer Tool</h1>
      <p>Analyze hook, pacing, caption formula, and remake structure without copying protected expression.</p>

      <section className="card">
        <span className="badge">MVP</span>
        <h2>New Analysis</h2>
        <form onSubmit={submitJob}>
          <p>
            <label>
              Email header
              <br />
              <input value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
          </p>
          <p>
            <label>
              Source Type
              <br />
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value as "url" | "upload")}>
                <option value="url">URL (YouTube only)</option>
                <option value="upload">Upload (binary)</option>
              </select>
            </label>
          </p>
          {sourceType === "url" ? (
            <p>
              <label>
                YouTube URL
                <br />
                <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} style={{ width: "100%" }} />
              </label>
            </p>
          ) : (
            <>
              <p>
                <label>
                  Choose File
                  <br />
                  <input type="file" accept="video/*" onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)} />
                </label>
              </p>
              <p style={{ fontSize: 13, color: "#5b6b5a" }}>
                Optional existing file key:
                <br />
                <input value={fileKey} onChange={(e) => setFileKey(e.target.value)} style={{ width: "100%" }} />
              </p>
              {uploadState ? <p style={{ fontSize: 13 }}>{uploadState}</p> : null}
            </>
          )}
          <button disabled={isSubmitting}>{isSubmitting ? "Submitting..." : "Analyze Clip"}</button>
        </form>
        {error ? <p style={{ color: "#9f1b1b" }}>Error: {error}</p> : null}
      </section>

      <section className="card">
        <h2>Processing Status</h2>
        {status ? (
          <p>
            job={status.job_id} | state={status.state} | stage={status.stage} | progress={status.progress}%
          </p>
        ) : (
          <p>No active job yet.</p>
        )}
      </section>

      <section className="card">
        <h2>Analysis Report</h2>
        {!report ? (
          <p>Report appears here when processing completes.</p>
        ) : (
          <>
            <p>
              Hook score: {report.hook_analysis.score} ({report.hook_analysis.verdict}) | Confidence: {report.confidence}
            </p>
            <p>Caption pattern: {report.caption_formula.pattern}</p>
            <p>
              Transcript source: {report.artifacts.transcript_source} | Feature source: {report.artifacts.feature_source_mode}
            </p>
            <PacingChart points={report.pacing_timeline} />
            <p>
              <button onClick={() => void requestExport("json")} disabled={isExporting !== ""}>
                {isExporting === "json" ? "Preparing JSON..." : "Export JSON"}
              </button>{" "}
              <button onClick={() => void requestExport("pdf")} disabled={isExporting !== ""}>
                {isExporting === "pdf" ? "Preparing PDF..." : "Export PDF"}
              </button>
            </p>
            {exportJsonUrl ? (
              <p>
                JSON:{" "}
                <a href={exportJsonUrl} target="_blank" rel="noreferrer">
                  download
                </a>
              </p>
            ) : null}
            {exportPdfUrl ? (
              <p>
                PDF:{" "}
                <a href={exportPdfUrl} target="_blank" rel="noreferrer">
                  download
                </a>
              </p>
            ) : null}
            <p>{report.remake_template.anti_plagiarism_notice}</p>
          </>
        )}
      </section>

      <section className="card">
        <h2>History + Usage</h2>
        <p>
          Plan: {usage?.plan ?? "-"} | Jobs used today: {usage?.jobs_used ?? 0}/{usage?.jobs_limit ?? 0}
        </p>
        <ul>
          {history.map((item) => (
            <li key={item.job_id}>
              {item.job_id} | {item.state} | confidence={item.confidence ?? "-"}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
