import time

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AnalysisJob, FeatureArtifact, TranscriptArtifact

client = TestClient(app)
headers = {"x-user-email": "creator@example.com"}


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200


def test_submit_and_get_status():
    payload = {
        "source_type": "url",
        "source_url": "https://youtu.be/dQw4w9WgXcQ",
        "confirm_rights": True,
    }
    response = client.post("/v1/jobs", headers=headers, json=payload)
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status_response = client.get(f"/v1/jobs/{job_id}", headers=headers)
    assert status_response.status_code == 200


def test_report_and_export_flow():
    payload = {
        "source_type": "url",
        "source_url": "https://youtu.be/dQw4w9WgXcQ",
        "confirm_rights": True,
    }
    submit = client.post("/v1/jobs", headers=headers, json=payload)
    assert submit.status_code == 200
    job_id = submit.json()["job_id"]

    # Job may complete inline fallback or after queue dispatch.
    for _ in range(10):
        status_response = client.get(f"/v1/jobs/{job_id}", headers=headers)
        assert status_response.status_code == 200
        if status_response.json()["state"] == "done":
            break
        time.sleep(0.2)

    report_response = client.get(f"/v1/reports/{job_id}", headers=headers)
    assert report_response.status_code == 200
    assert "hook_analysis" in report_response.json()
    assert "artifacts" in report_response.json()
    assert "transcript_source" in report_response.json()["artifacts"]

    artifacts_response = client.get(f"/v1/reports/{job_id}/artifacts", headers=headers)
    assert artifacts_response.status_code == 200
    assert "transcript" in artifacts_response.json()
    timeline_response = client.get(f"/v1/reports/{job_id}/timeline", headers=headers)
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()["timeline"]
    if timeline:
        assert "cut_frequency" in timeline[0]
        assert "speech_rate_wpm" in timeline[0]

    export_response = client.post(
        f"/v1/reports/{job_id}/export",
        headers=headers,
        json={"format": "json"},
    )
    assert export_response.status_code == 200
    download_url = export_response.json()["download_url"]

    download_response = client.get(download_url, headers=headers)
    assert download_response.status_code == 200


def test_upload_path_flow():
    presign = client.post("/v1/uploads/presign", headers=headers, json={"filename": "clip.mp4"})
    assert presign.status_code == 200
    file_key = presign.json()["file_key"]
    upload_url = presign.json()["upload_url"]

    upload = client.put(upload_url, headers={"x-user-email": headers["x-user-email"]}, content=b"fake-video-bytes")
    assert upload.status_code == 204

    submit = client.post(
        "/v1/jobs",
        headers=headers,
        json={"source_type": "upload", "file_key": file_key, "duration_sec": 30, "confirm_rights": True},
    )
    assert submit.status_code == 200
    job_id = submit.json()["job_id"]

    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        assert job is not None
        t_art = db.query(TranscriptArtifact).filter(TranscriptArtifact.job_id == job_id).first()
        f_art = db.query(FeatureArtifact).filter(FeatureArtifact.job_id == job_id).first()
        assert t_art is not None
        assert f_art is not None
        assert isinstance(f_art.timeline_json, list)
    finally:
        db.close()


def test_maintenance_cleanup_endpoint():
    response = client.post("/v1/maintenance/cleanup", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "queued" in body
