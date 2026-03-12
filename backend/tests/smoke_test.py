"""
tests/smoke_test.py — Live smoke tests against the running backend.

Run:
    python tests/smoke_test.py
or:
    pytest tests/smoke_test.py -v -s

Requires backend running on http://localhost:8000
"""
from __future__ import annotations

import sys
import httpx

BASE = "http://localhost:8000"
passed: list[str] = []
failed: list[str] = []


def check(name: str, resp: httpx.Response, expected_status: int | None = None, check_fn=None):
    try:
        ok = (resp.status_code == expected_status) if expected_status is not None else True
        if ok and check_fn:
            ok = bool(check_fn(resp))
    except Exception as exc:
        ok = False
        name = f"{name} [exception: {exc}]"
    label = "PASS" if ok else "FAIL"
    print(f"  [{label}] {name}  (HTTP {resp.status_code})")
    (passed if ok else failed).append(name)


def run():
    with httpx.Client(base_url=BASE, timeout=30) as c:

        # ── INFRA ──────────────────────────────────────────────────────
        print("=== INFRA ===")
        r = c.get("/health")
        check("GET /health => 200 + ok", r, 200, lambda r: r.json()["status"] == "ok")

        r = c.get("/docs")
        check("GET /docs => 200", r, 200)

        r = c.get("/redoc")
        check("GET /redoc => 200", r, 200)

        r = c.get("/openapi.json")
        oas = r.json() if r.status_code == 200 else {}
        check("GET /openapi.json => 200 with paths", r, 200, lambda r: "paths" in r.json())
        n_routes = len(oas.get("paths", {}))
        print(f"       {n_routes} paths registered in OpenAPI spec")

        # ── PUBLIC COMPLAINT ENDPOINTS ─────────────────────────────────
        print()
        print("=== PUBLIC COMPLAINT ENDPOINTS ===")

        r = c.get("/api/v1/complaints/MCD-00000000-XXXXX")
        check("GET /complaints/bad-grievance-id => 404", r, 404)

        r = c.post("/api/v1/complaints", json={})
        check("POST /complaints empty body => 422", r, 422)

        r = c.post("/api/v1/complaints", json={
            "raw_text": "test", "lat": 28.6, "lng": 77.2, "channel": "BAD"
        })
        check("POST /complaints invalid channel enum => 422", r, 422)

        # Real submission
        print("  [submitting real complaint to Supabase…]")
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Broken streetlight near Rohini Sector 7 main junction causing safety hazard at night",
            "lat": 28.7041,
            "lng": 77.1025,
            "channel": "web",
            "citizen_email": "testcitizen@example.com",
        }, timeout=30)

        gid = cid = None
        if r.status_code == 201:
            body = r.json()
            gid = body.get("grievance_id", "")
            cid = body.get("id", "")
            check(
                f"POST /complaints => 201, grievance_id={gid}",
                r, 201,
                lambda r: r.json().get("grievance_id", "").startswith("MCD-"),
            )
            cat = body.get("category")
            urg = body.get("urgency")
            print(f"       category={cat}  urgency={urg}")
        else:
            check("POST /complaints => 201", r, 201)
            print(f"       Response body: {r.text[:400]}")

        if gid:
            r2 = c.get(f"/api/v1/complaints/{gid}")
            check(
                f"GET /complaints/{{grievance_id}} => 200",
                r2, 200,
                lambda r: r.json().get("grievance_id") == gid,
            )

        if cid:
            r3 = c.get(f"/api/v1/complaints/{cid}")
            check(
                "GET /complaints/{uuid} => 200",
                r3, 200,
                lambda r: r.json().get("id") == cid,
            )
            if r3.status_code == 200:
                d = r3.json()
                print(f"       status={d.get('status')}  sla_deadline={str(d.get('sla_deadline', ''))[:10]}")
                print(f"       timeline_events={len(d.get('timeline', []))}")

        # Second complaint — different category (drainage)
        r = c.post("/api/v1/complaints", json={
            "raw_text": "Sewage overflow on road near Lajpat Nagar market, foul smell and health risk",
            "lat": 28.5672,
            "lng": 77.2434,
            "channel": "web",
        }, timeout=30)
        check("POST /complaints drainage complaint => 201", r, 201)
        if r.status_code == 201:
            cat2 = r.json().get("category")
            print(f"       category={cat2}")

        # ── AUTH PROTECTION ────────────────────────────────────────────
        print()
        print("=== AUTH PROTECTION ===")

        no_auth_gets = [
            "/api/v1/complaints",
            "/api/v1/analytics/hotspots",
            "/api/v1/analytics/sla-compliance",
            "/api/v1/analytics/complaint-volume",
        ]
        for path in no_auth_gets:
            r = c.get(path)
            check(f"GET {path} no-auth => 401/403", r, None,
                  lambda r: r.status_code in (401, 403))

        for path in ["/api/v1/complaints", "/api/v1/analytics/hotspots"]:
            r = c.get(path, headers={"Authorization": "Bearer fake.jwt.invalid"})
            check(f"GET {path} bad-JWT => 401/403", r, None,
                  lambda r: r.status_code in (401, 403))

        # ── WEBHOOK SECURITY ───────────────────────────────────────────
        print()
        print("=== WEBHOOK SECURITY ===")

        r = c.post("/telegram/webhook", json={"update_id": 1})
        check("POST /telegram/webhook no-secret => 403", r, 403)

        r = c.post("/telegram/webhook", json={"update_id": 1},
                   headers={"X-Telegram-Bot-Api-Secret-Token": "wrongsecret"})
        check("POST /telegram/webhook wrong-secret => 403", r, 403)

        r = c.post("/internal/run-predictive-agent",
                   headers={"x-internal-key": "wrongkey"})
        check("POST /internal/run-predictive-agent wrong-key => 401", r, 401)

        # ── INPUT VALIDATION / SECURITY ────────────────────────────────
        print()
        print("=== INPUT VALIDATION / INJECTION CHECKS ===")

        sql_injection = "'; DROP TABLE complaints; --"
        r = c.post("/api/v1/complaints", json={
            "raw_text": sql_injection, "lat": 28.6, "lng": 77.2, "channel": "web"
        }, timeout=30)
        check("POST /complaints SQL injection string => not 500", r, None,
              lambda r: r.status_code != 500)
        print(f"       SQL injection payload => {r.status_code}")

        xss_payload = "<script>alert('xss')</script>"
        r = c.post("/api/v1/complaints", json={
            "raw_text": xss_payload, "lat": 28.6, "lng": 77.2, "channel": "web"
        }, timeout=30)
        check("POST /complaints XSS payload => not 500", r, None,
              lambda r: r.status_code != 500)
        print(f"       XSS payload => {r.status_code}")

        # Very long text
        r = c.post("/api/v1/complaints", json={
            "raw_text": "A" * 10000, "lat": 28.6, "lng": 77.2, "channel": "web"
        }, timeout=30)
        check("POST /complaints 10k char text => not 500", r, None,
              lambda r: r.status_code != 500)
        print(f"       10k char payload => {r.status_code}")

    # ── Summary ────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print(f"  Results: {len(passed)} PASSED   {len(failed)} FAILED")
    print("=" * 55)
    if failed:
        print("FAILED:")
        for f in failed:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("  All checks PASSED ✓")


if __name__ == "__main__":
    run()
