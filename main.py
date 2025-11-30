# Command to run: uvicorn main:app --reload

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from collections import Counter
from pathlib import Path
import csv, io, re, uvicorn, random

app = FastAPI(title="CSU Scheduler API")

# -----------------------------------------------------------------------------
# CORS (allow local frontend)
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Expected Columns
# -----------------------------------------------------------------------------
COURSE_COLS = [
    "Course", 
    "Section", 
    "Days", 
    "StartTime", 
    "EndTime", 
    "Room",
    "Min # of SPTs Required"
]

STAFF_COLS = [
    "Name:",
    "Partner Preference 1:",
    "Partner Preference 2:",
    "Partner Preference 3:",
    "1st Choice",
    "2nd Choice",
    "9:10AM-11:05AM",
    "11:20AM-1:15PM",
    "1:30PM-2:20PM",
    "Veteran?"
]

TIME_SLOTS = [
    "9:10AM-11:05AM",
    "11:20AM-1:15PM",
    "1:30PM-2:20PM"
]

LAST_COURSE_ROWS: List[Dict[str, Any]] = []
LAST_STAFF_ROWS: List[Dict[str, Any]] = []

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def _normalize_header(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (s or '').strip().lower())

def _parse_csv_upload(file: UploadFile) -> List[Dict[str, str]]:
    data = file.file.read()
    text = data.decode("utf-8-sig", errors="ignore")
    delimiter = "\t" if "\t" in text else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader if any(row.values())]

def _truthy(val) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in {"1","y","yes","true","t","x","✓","available","avail"}

def _normalize_name(x: str) -> str:
    return (x or "").strip()

def _score_candidate(staff: Dict[str, Any], course_row: Dict[str, Any], already_in_session_names: set) -> int:
    score = 0
    course_name = str(course_row.get("Course", "")).strip().lower()
    if course_name and str(staff.get("1st Choice", "")).strip().lower() == course_name:
        score += 6
    if course_name and str(staff.get("2nd Choice", "")).strip().lower() == course_name:
        score += 3
    prefs = {
        _normalize_name(staff.get("Partner Preference 1:", "")),
        _normalize_name(staff.get("Partner Preference 2:", "")),
        _normalize_name(staff.get("Partner Preference 3:", "")),
    }
    overlap = prefs & already_in_session_names
    if overlap:
        score += 4 * len(overlap)
    if _truthy(staff.get("Veteran?", "")):
        score += 2
    return score

# -----------------------------------------------------------------------------
# Scheduler Logic
# -----------------------------------------------------------------------------
def _generate_schedule(course_rows: List[Dict[str, Any]], staff_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    staff_by_name = {}
    staff_load = Counter()

    # --- Build staff metadata ---
    for s in staff_rows:
        name = _normalize_name(s.get("Name:", ""))
        if not name:
            continue
        s["_name"] = name
        s["_avail"] = {slot: _truthy(s.get(slot, "")) for slot in TIME_SLOTS}
        s["_prefs"] = {
            _normalize_name(s.get("Partner Preference 1:", "")),
            _normalize_name(s.get("Partner Preference 2:", "")),
            _normalize_name(s.get("Partner Preference 3:", "")),
        }
        s["_veteran"] = _truthy(s.get("Veteran?", ""))
        staff_by_name[name] = s

    # --- Build course sessions ---
    sessions = []
    for c in course_rows:
        slot = f'{str(c.get("StartTime","")).strip()}-{str(c.get("EndTime","")).strip()}'
        block_map = {
            "9:10AM-9:55AM": "9:10AM-11:05AM",
            "9:10AM-10:00AM": "9:10AM-11:05AM",
            "10:15AM-11:05AM": "9:10AM-11:05AM",
            "11:20AM-12:05PM": "11:20AM-1:15PM",
            "11:20AM-12:10PM": "11:20AM-1:15PM",
            "12:25PM-1:15PM": "11:20AM-1:15PM",
            "1:30PM-2:15PM": "1:30PM-2:20PM",
            "2:25PM-3:30PM": "1:30PM-2:20PM",
        }
        slot = block_map.get(slot, slot)
        if slot in TIME_SLOTS:
            sessions.append((slot, c))

    results = {}
    placed_overall = set()

    # --- STEP 1: Base assignment ---
    for slot, course_row in sessions:
        key = f'{slot}|{course_row.get("Course","")}|{course_row.get("Section","")}'
        results[key] = {"meta": course_row, "assigned": []}

        # find eligible candidates
        candidates = [
            s for s in staff_by_name.values()
            if s["_avail"].get(slot, False) and s["_name"] not in placed_overall
        ]

        while len(results[key]["assigned"]) < 2 and candidates:
            current_names = {a["name"] for a in results[key]["assigned"]}
            scored = [( _score_candidate(s, course_row, current_names), s) for s in candidates]
            scored.sort(key=lambda t: t[0], reverse=True)
            _, chosen = scored[0]

            cname = chosen["_name"]
            results[key]["assigned"].append({"name": cname, "veteran": bool(chosen["_veteran"])})
            staff_load[cname] += 1
            placed_overall.add(cname)
            candidates = [s for s in candidates if s["_name"] != cname]

        # ensure at least one veteran
        has_vet = any(a["veteran"] for a in results[key]["assigned"])
        if not has_vet:
            vet_candidates = [
                s for s in staff_by_name.values()
                if s["_veteran"] and s["_avail"].get(slot, False) and s["_name"] not in placed_overall
            ]
            if vet_candidates:
                v = vet_candidates[0]
                results[key]["assigned"].append({"name": v["_name"], "veteran": True})
                placed_overall.add(v["_name"])
                staff_load[v["_name"]] += 1

    # --- STEP 2: Fill unassigned SPTs into underfilled sessions ---
    unassigned = [s for s in staff_by_name.values() if s["_name"] not in placed_overall]
    for s in unassigned:
        open_sessions = [
            k for k, v in results.items()
            if len(v["assigned"]) < 3
        ]
        if not open_sessions:
            break
        key = random.choice(open_sessions)
        results[key]["assigned"].append({"name": s["_name"], "veteran": bool(s["_veteran"])})
        placed_overall.add(s["_name"])
        staff_load[s["_name"]] += 1

    # --- STEP 3: Veteran rebalancing ---
    veterans = [s for s in staff_by_name.values() if s["_veteran"]]
    veteran_names = {s["_name"] for s in veterans}

    for key, info in results.items():
        assigned = info["assigned"]
        if not any(a["veteran"] for a in assigned):
            # find available veteran not yet assigned
            available_vet = next(
                (v for v in veterans if v["_name"] not in placed_overall),
                None
            )
            if available_vet:
                info["assigned"].append({"name": available_vet["_name"], "veteran": True})
                placed_overall.add(available_vet["_name"])
                staff_load[available_vet["_name"]] += 1
            else:
                # try swapping from another session that has ≥2 veterans
                donor = next(
                    (k2 for k2, v2 in results.items() if sum(a["veteran"] for a in v2["assigned"]) >= 2),
                    None
                )
                if donor:
                    donor_vet = next(a for a in results[donor]["assigned"] if a["veteran"])
                    results[donor]["assigned"].remove(donor_vet)
                    info["assigned"].append(donor_vet)

    return {"assignments": results, "staff_load": dict(staff_load)}

# -----------------------------------------------------------------------------
# API: Upload Rosters
# -----------------------------------------------------------------------------
@app.post("/api/upload-rosters")
async def upload_rosters(course_roster: UploadFile = File(...), staff_roster: UploadFile = File(...)):
    course_rows = _parse_csv_upload(course_roster)
    staff_rows = _parse_csv_upload(staff_roster)
    if not course_rows or not staff_rows:
        raise HTTPException(status_code=400, detail="One or both CSV files are empty.")

    def _check_headers(rows, required, label):
        got = {_normalize_header(k) for k in rows[0].keys()}
        missing = [c for c in required if _normalize_header(c) not in got]
        if missing:
            raise HTTPException(status_code=400, detail=f"{label} missing columns: {', '.join(missing)}")

    _check_headers(course_rows, COURSE_COLS, "Course")
    _check_headers(staff_rows, STAFF_COLS, "Staff")

    global LAST_COURSE_ROWS, LAST_STAFF_ROWS
    LAST_COURSE_ROWS, LAST_STAFF_ROWS = course_rows, staff_rows
    return {"ok": True, "course_rows": len(course_rows), "staff_rows": len(staff_rows)}

# -----------------------------------------------------------------------------
# API: Generate Schedule
# -----------------------------------------------------------------------------
class ScheduleRequest(BaseModel):
    course_rows: List[Dict[str, Any]] | None = None
    staff_rows: List[Dict[str, Any]] | None = None

@app.post("/api/generate-schedule")
def api_generate_schedule(req: ScheduleRequest | None = Body(default=None)):
    req = req or ScheduleRequest()
    course_rows = req.course_rows or LAST_COURSE_ROWS
    staff_rows = req.staff_rows or LAST_STAFF_ROWS
    if not course_rows or not staff_rows:
        raise HTTPException(status_code=400, detail="No data uploaded.")
    return _generate_schedule(course_rows, staff_rows)

# -----------------------------------------------------------------------------
# Misc endpoints
# -----------------------------------------------------------------------------
@app.post("/api/submit")
async def submit_schedule(request: Request):
    data = await request.json()
    return {"message": f"Schedule received for {data.get('taName')} on {data.get('days')}"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# Serve frontend
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
