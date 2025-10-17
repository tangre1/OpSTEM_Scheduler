# Command to run: uvicorn main:app --reload

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from collections import Counter
import csv, io, re, uvicorn

app = FastAPI(title="CSU Scheduler API")

# -----------------------------------------------------------------------------
# CORS (allow local frontend)
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Expected Columns
# -----------------------------------------------------------------------------
COURSE_COLS = [
    "Course", "Section", "Days", "StartTime", "EndTime", "Room",
    "Min # of SPTs Required"
]
STAFF_COLS = [
    "Name:",
    "Partner Preference 1:", "Partner Preference 2:", "Partner Preference 3:",
    "1st Choice", "2nd Choice",
    "9:10AM-10:00AM", "10:15AM-11:05AM", "11:20AM-12:10PM",
    "12:25PM-1:15PM", "1:30PM-2:20PM", "2:35PM-3:25PM",
    "Veteran?"
]
TIME_SLOTS = [
    "9:10AM-10:00AM", "10:15AM-11:05AM", "11:20AM-12:10PM",
    "12:25PM-1:15PM", "1:30PM-2:20PM", "2:35PM-3:25PM"
]

# -----------------------------------------------------------------------------
# In-memory storage
# -----------------------------------------------------------------------------
LAST_COURSE_ROWS: List[Dict[str, Any]] = []
LAST_STAFF_ROWS: List[Dict[str, Any]] = []

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def _normalize_header(s: str) -> str:
    """Lowercase, strip, remove punctuation and extra spaces."""
    return re.sub(r'[^a-z0-9]+', '', (s or '').strip().lower())

def _parse_csv_upload(file: UploadFile) -> List[Dict[str, str]]:
    """Read CSV (auto-detect tab vs comma, handle BOM)."""
    data = file.file.read()
    text = data.decode("utf-8-sig", errors="ignore")
    delimiter = "\t" if "\t" in text else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader if any(row.values())]

def _truthy(val) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in {"1", "y", "yes", "true", "t", "x", "✓", "available", "avail"}

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
    staff_by_name: Dict[str, Dict[str, Any]] = {}
    staff_load = Counter()

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

    sessions = []
    for c in course_rows:
        slot = f'{str(c.get("StartTime","")).strip()}-{str(c.get("EndTime","")).strip()}'
        if slot not in TIME_SLOTS:
            continue
        try:
            need = int(str(c.get("Min # of SPTs Required", "1")).strip())
        except ValueError:
            need = 1
        sessions.append((slot, c, max(1, need)))

    def _available_count(slot, _):
        return sum(1 for s in staff_by_name.values() if s["_avail"].get(slot, False))

    sessions.sort(key=lambda x: (-x[2], _available_count(x[0], x[1])))

    results: Dict[str, Any] = {}
    placed_per_slot = {slot: set() for slot in TIME_SLOTS}

    for slot, course_row, need in sessions:
        key = f'{slot}|{course_row.get("Course","")}|{course_row.get("Section","")}'
        results[key] = {"meta": course_row, "assigned": []}
        candidates = [s for s in staff_by_name.values() if s["_avail"].get(slot, False)]

        while len(results[key]["assigned"]) < need and candidates:
            current_names = placed_per_slot[slot]
            scored = []
            for s in candidates:
                base = _score_candidate(s, course_row, current_names)
                bonus = max(0, 4 - staff_load[s["_name"]])
                scored.append((base + bonus, s))
            scored.sort(key=lambda t: t[0], reverse=True)

            _, chosen = scored[0]
            cname = chosen["_name"]
            results[key]["assigned"].append({"name": cname, "veteran": bool(chosen["_veteran"])})
            staff_load[cname] += 1
            placed_per_slot[slot].add(cname)
            candidates = [s for s in candidates if s["_name"] != cname]

            if len(results[key]["assigned"]) < need:
                for p in chosen["_prefs"]:
                    ps = staff_by_name.get(p)
                    if not ps or ps["_name"] in placed_per_slot[slot]:
                        continue
                    if ps in candidates:
                        results[key]["assigned"].append({"name": ps["_name"], "veteran": bool(ps["_veteran"])})
                        staff_load[ps["_name"]] += 1
                        placed_per_slot[slot].add(ps["_name"])
                        candidates = [s for s in candidates if s["_name"] != ps["_name"]]
                        if len(results[key]["assigned"]) >= need:
                            break

        if len(results[key]["assigned"]) < need:
            remaining = [
                s for s in staff_by_name.values()
                if s["_avail"].get(slot, False) and s["_name"] not in placed_per_slot[slot]
            ]
            for s in remaining:
                if len(results[key]["assigned"]) >= need:
                    break
                results[key]["assigned"].append({"name": s["_name"], "veteran": bool(s["_veteran"])})
                staff_load[s["_name"]] += 1
                placed_per_slot[slot].add(s["_name"])

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

    def _check_headers(rows: List[Dict[str, Any]], required: List[str], label: str):
        if not rows:
            raise HTTPException(status_code=400, detail=f"{label} CSV is empty.")
        got = {_normalize_header(k) for k in rows[0].keys()}
        missing = [c for c in required if _normalize_header(c) not in got]
        if missing:
            raise HTTPException(status_code=400, detail=f"{label} missing columns: {', '.join(missing)}")

    _check_headers(course_rows, COURSE_COLS, "Course")
    _check_headers(staff_rows, STAFF_COLS, "Staff")

    global LAST_COURSE_ROWS, LAST_STAFF_ROWS
    LAST_COURSE_ROWS = course_rows
    LAST_STAFF_ROWS = staff_rows

    return {"ok": True, "course_rows": len(course_rows), "staff_rows": len(staff_rows)}

# -----------------------------------------------------------------------------
# API: Generate Schedule
# -----------------------------------------------------------------------------
class ScheduleRequest(BaseModel):
    course_rows: List[Dict[str, Any]] | None = None
    staff_rows: List[Dict[str, Any]] | None = None

from fastapi import Body

@app.post("/api/generate-schedule")
def api_generate_schedule(req: ScheduleRequest | None = Body(default=None)):
    # allow empty body
    if req is None:
        req = ScheduleRequest()

    course_rows = req.course_rows if req.course_rows else LAST_COURSE_ROWS
    staff_rows = req.staff_rows if req.staff_rows else LAST_STAFF_ROWS

    if not course_rows or not staff_rows:
        raise HTTPException(status_code=400, detail="No data uploaded.")

    schedule = _generate_schedule(course_rows, staff_rows)
    return schedule

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
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
