import asyncio
import json
import sys
from dataclasses import dataclass

import requests
import websockets


API_BASE = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/generate"


EXPECTED_COLS = [
    "Company Name",
    "Contact Name",
    "Title",
    "Email",
    "Phone",
    "Location",
    "Company Size",
    "Status",
]


@dataclass
class TestResult:
    name: str
    ok: bool
    details: str = ""


def health_check() -> None:
    r = requests.get(f"{API_BASE}/health", timeout=5)
    r.raise_for_status()
    data = r.json()
    assert data.get("status") == "ok", f"unexpected health payload: {data}"


async def ws_pipeline() -> tuple[str, list[dict]]:
    payload = {
        "industry": "SaaS",
        "location": "Jordan",
        "lead_type": "B2B",
        "target_role": "CEO",
        "company_size": "10-50",
        "keywords": "software",
        "num_leads": 1,
    }

    messages: list[dict] = []
    session_id = ""
    async with websockets.connect(WS_URL, open_timeout=10) as ws:
        await ws.send(json.dumps(payload))
        idx = 0
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
            except asyncio.TimeoutError:
                break
            idx += 1
            data = json.loads(raw)
            print(f"[{idx}] {data}")
            messages.append(data)
            if data.get("status") == "started" and data.get("session_id"):
                session_id = data["session_id"]
            if data.get("status") in ("ready", "error"):
                if data.get("session_id"):
                    session_id = data["session_id"]
                break

    if not session_id:
        raise AssertionError("No session_id received from websocket messages.")
    return session_id, messages


def download_csv(session_id: str) -> str:
    r = requests.get(f"{API_BASE}/download/{session_id}", timeout=30)
    r.raise_for_status()
    assert "text/csv" in r.headers.get("content-type", ""), r.headers.get("content-type")
    return r.text


def verify_csv(csv_text: str) -> None:
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    assert len(lines) >= 2, f"CSV has no data rows. Lines={len(lines)}"
    header = lines[0].split(",")
    assert header == EXPECTED_COLS, f"Header mismatch.\nExpected={EXPECTED_COLS}\nGot={header}"


def main() -> int:
    results: list[TestResult] = []

    try:
        health_check()
        results.append(TestResult("Health check", True))
    except Exception as e:
        results.append(TestResult("Health check", False, str(e)))
        print(results[-1])
        return 1

    try:
        session_id, _messages = asyncio.run(ws_pipeline())
        results.append(TestResult("WebSocket pipeline — got session_id", True, session_id))
    except Exception as e:
        results.append(TestResult("WebSocket pipeline — got session_id", False, str(e)))
        session_id = ""

    csv_text = ""
    if session_id:
        try:
            csv_text = download_csv(session_id)
            results.append(TestResult("CSV download", True, "\n".join(csv_text.splitlines()[:3])))
        except Exception as e:
            results.append(TestResult("CSV download", False, str(e)))

    if csv_text:
        try:
            verify_csv(csv_text)
            results.append(TestResult("CSV columns + data row", True))
        except Exception as e:
            results.append(TestResult("CSV columns + data row", False, str(e)))

    print("\n==== SUMMARY ====")
    for r in results:
        mark = "✓" if r.ok else "✗"
        extra = f" — {r.details}" if r.details else ""
        print(f"{mark} {r.name}{extra}")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

