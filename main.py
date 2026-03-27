from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from collections import Counter
from pathlib import Path
import csv
import io
import re
import uvicorn
import random

app = FastAPI(title="CSU Scheduler API")

# -----------------------------------------------------------------------------
# CORS
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
    "Min # of SPTs Required",
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
    "Veteran?",
]

TIME_SLOTS = [
    "9:10AM-11:05AM",
    "11:20AM-1:15PM",
    "1:30PM-2:20PM",
]

LAST_COURSE_ROWS: List[Dict[str, Any]] = []
LAST_STAFF_ROWS: List[Dict[str, Any]] = []

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def _normalize_header(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").strip().lower())


def _parse_csv_upload(file: UploadFile) -> List[Dict[str, str]]:
    data = file.file.read()
    text = data.decode("utf-8-sig", errors="ignore")
    delimiter = "\t" if "\t" in text else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader if any(row.values())]


def _truthy(val: Any) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in {"1", "y", "yes", "true", "t", "x", "✓", "available", "avail"}


def _normalize_name(x: str) -> str:
    return (x or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _score_candidate(
    staff: Dict[str, Any],
    course_row: Dict[str, Any],
    already_in_session_names: set,
) -> int:
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
    prefs.discard("")

    overlap = prefs & already_in_session_names
    if overlap:
        score += 4 * len(overlap)

    if _truthy(staff.get("Veteran?", "")):
        score += 2

    return score


def _normalize_time_block(start_time: str, end_time: str) -> str:
    slot = f"{str(start_time).strip()}-{str(end_time).strip()}"
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
    return block_map.get(slot, slot)

# -----------------------------------------------------------------------------
# Scheduler Logic
# -----------------------------------------------------------------------------
def _generate_schedule(course_rows: List[Dict[str, Any]], staff_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    staff_by_name: Dict[str, Dict[str, Any]] = {}
    staff_load = Counter()

    # --- Build staff metadata ---
    for s in staff_rows:
        name = _normalize_name(s.get("Name:", ""))
        if not name:
            continue

        s_copy = dict(s)
        s_copy["_name"] = name
        s_copy["_avail"] = {slot: _truthy(s_copy.get(slot, "")) for slot in TIME_SLOTS}
        s_copy["_prefs"] = {
            _normalize_name(s_copy.get("Partner Preference 1:", "")),
            _normalize_name(s_copy.get("Partner Preference 2:", "")),
            _normalize_name(s_copy.get("Partner Preference 3:", "")),
        }
        s_copy["_prefs"].discard("")
        s_copy["_veteran"] = _truthy(s_copy.get("Veteran?", ""))
        staff_by_name[name] = s_copy

    # --- Build course sessions ---
    sessions = []
    for c in course_rows:
        slot = _normalize_time_block(c.get("StartTime", ""), c.get("EndTime", ""))
        if slot in TIME_SLOTS:
            sessions.append((slot, c))

    results: Dict[str, Any] = {}
    placed_overall = set()

    # --- STEP 1: Base assignment ---
    for slot, course_row in sessions:
        key = f'{slot}|{course_row.get("Course", "")}|{course_row.get("Section", "")}'
        results[key] = {"meta": course_row, "assigned": []}

        min_required = max(_safe_int(course_row.get("Min # of SPTs Required", 0), 0), 0)
        target_base = min(min_required if min_required > 0 else 2, 3)

        candidates = [
            s
            for s in staff_by_name.values()
            if s["_avail"].get(slot, False) and s["_name"] not in placed_overall
        ]

        while len(results[key]["assigned"]) < target_base and candidates:
            current_names = {a["name"] for a in results[key]["assigned"]}
            scored = [(_score_candidate(s, course_row, current_names), s) for s in candidates]
            scored.sort(key=lambda t: t[0], reverse=True)
            _, chosen = scored[0]

            cname = chosen["_name"]
            results[key]["assigned"].append(
                {"name": cname, "veteran": bool(chosen["_veteran"])}
            )
            staff_load[cname] += 1
            placed_overall.add(cname)
            candidates = [s for s in candidates if s["_name"] != cname]

        # ensure at least one veteran if possible
        has_vet = any(a["veteran"] for a in results[key]["assigned"])
        if not has_vet:
            vet_candidates = [
                s
                for s in staff_by_name.values()
                if s["_veteran"]
                and s["_avail"].get(slot, False)
                and s["_name"] not in placed_overall
            ]
            if vet_candidates and len(results[key]["assigned"]) < 3:
                v = vet_candidates[0]
                results[key]["assigned"].append({"name": v["_name"], "veteran": True})
                placed_overall.add(v["_name"])
                staff_load[v["_name"]] += 1

    # --- STEP 2: Fill unassigned staff into underfilled sessions ---
    unassigned = [s for s in staff_by_name.values() if s["_name"] not in placed_overall]
    for s in unassigned:
        open_sessions = []
        for k, v in results.items():
            min_required = _safe_int(v["meta"].get("Min # of SPTs Required", 0), 0)
            cap = min(max(min_required, 1), 3)
            if len(v["assigned"]) < cap:
                open_sessions.append(k)

        if not open_sessions:
            break

        key = random.choice(open_sessions)
        results[key]["assigned"].append(
            {"name": s["_name"], "veteran": bool(s["_veteran"])}
        )
        placed_overall.add(s["_name"])
        staff_load[s["_name"]] += 1

    # --- STEP 3: Veteran rebalancing ---
    veterans = [s for s in staff_by_name.values() if s["_veteran"]]

    for key, info in results.items():
        assigned = info["assigned"]
        if any(a["veteran"] for a in assigned):
            continue

        slot = _normalize_time_block(
            info["meta"].get("StartTime", ""),
            info["meta"].get("EndTime", ""),
        )

        available_unplaced_vet = next(
            (
                v
                for v in veterans
                if v["_name"] not in placed_overall and v["_avail"].get(slot, False)
            ),
            None,
        )

        if available_unplaced_vet and len(assigned) < 3:
            info["assigned"].append(
                {"name": available_unplaced_vet["_name"], "veteran": True}
            )
            placed_overall.add(available_unplaced_vet["_name"])
            staff_load[available_unplaced_vet["_name"]] += 1
            continue

        donor = next(
            (
                k2
                for k2, v2 in results.items()
                if k2 != key and sum(a["veteran"] for a in v2["assigned"]) >= 2
            ),
            None,
        )
        if donor:
            donor_vet = next((a for a in results[donor]["assigned"] if a["veteran"]), None)
            if donor_vet:
                results[donor]["assigned"].remove(donor_vet)
                info["assigned"].append(donor_vet)

    return {"assignments": results, "staff_load": dict(staff_load)}

# -----------------------------------------------------------------------------
# Metrics + Explanation
# -----------------------------------------------------------------------------
def _compute_schedule_metrics(
    schedule_result: Dict[str, Any],
    staff_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    assignments = schedule_result.get("assignments", {})
    staff_by_name: Dict[str, Dict[str, Any]] = {}

    for s in staff_rows:
        name = _normalize_name(s.get("Name:", ""))
        if name:
            staff_by_name[name] = s

    total_sessions = len(assignments)
    underfilled_sessions = 0
    veteran_covered_sessions = 0
    first_choice_matches = 0
    second_choice_matches = 0
    partner_preference_matches = 0
    total_assigned = 0
    assigned_names = set()

    for _, info in assignments.items():
        meta = info.get("meta", {})
        assigned = info.get("assigned", [])
        course_name = str(meta.get("Course", "")).strip().lower()
        min_required = _safe_int(meta.get("Min # of SPTs Required", "0"), 0)

        if len(assigned) < min_required:
            underfilled_sessions += 1

        if any(a.get("veteran") for a in assigned):
            veteran_covered_sessions += 1

        current_names = {a.get("name") for a in assigned if a.get("name")}

        for a in assigned:
            name = a.get("name")
            if not name:
                continue

            total_assigned += 1
            assigned_names.add(name)
            staff = staff_by_name.get(name, {})

            first_choice = str(staff.get("1st Choice", "")).strip().lower()
            second_choice = str(staff.get("2nd Choice", "")).strip().lower()

            if first_choice and first_choice == course_name:
                first_choice_matches += 1
            elif second_choice and second_choice == course_name:
                second_choice_matches += 1

            prefs = {
                _normalize_name(staff.get("Partner Preference 1:", "")),
                _normalize_name(staff.get("Partner Preference 2:", "")),
                _normalize_name(staff.get("Partner Preference 3:", "")),
            }
            prefs.discard("")

            if prefs & (current_names - {name}):
                partner_preference_matches += 1

    unassigned_staff = [
        _normalize_name(s.get("Name:", ""))
        for s in staff_rows
        if _normalize_name(s.get("Name:", ""))
        and _normalize_name(s.get("Name:", "")) not in assigned_names
    ]

    coverage_rate = (
        0
        if total_sessions == 0
        else round(((total_sessions - underfilled_sessions) / total_sessions) * 100, 1)
    )
    veteran_coverage_rate = (
        0
        if total_sessions == 0
        else round((veteran_covered_sessions / total_sessions) * 100, 1)
    )

    return {
        "total_sessions": total_sessions,
        "underfilled_sessions": underfilled_sessions,
        "coverage_rate": coverage_rate,
        "veteran_covered_sessions": veteran_covered_sessions,
        "veteran_coverage_rate": veteran_coverage_rate,
        "first_choice_matches": first_choice_matches,
        "second_choice_matches": second_choice_matches,
        "partner_preference_matches": partner_preference_matches,
        "total_assigned": total_assigned,
        "unassigned_staff_count": len(unassigned_staff),
        "unassigned_staff": unassigned_staff,
    }

def _build_placeholder_explanation(
    schedule_result: Dict[str, Any],
    metrics: Dict[str, Any],
    coordinator_notes: str | None = None,
) -> Dict[str, Any]:
    strengths = []
    tradeoffs = []
    recommendations = []
    priorities_review = []

    if metrics["coverage_rate"] == 100:
        strengths.append("All sessions met minimum staffing requirements.")
    else:
        tradeoffs.append(
            f"{metrics['underfilled_sessions']} session(s) did not meet minimum staffing requirements."
        )

    if metrics["veteran_coverage_rate"] >= 80:
        strengths.append("Veteran coverage is strong across most sessions.")
    else:
        tradeoffs.append("Veteran coverage is limited in some sessions.")

    if metrics["first_choice_matches"] > 0:
        strengths.append(
            f"{metrics['first_choice_matches']} assignment(s) matched a staff member's first choice."
        )

    if metrics["partner_preference_matches"] > 0:
        strengths.append(
            f"{metrics['partner_preference_matches']} assignment(s) satisfied partner preferences."
        )

    if metrics["unassigned_staff_count"] > 0:
        tradeoffs.append(
            f"{metrics['unassigned_staff_count']} staff member(s) remain unassigned."
        )
        recommendations.append(
            "Review unassigned staff for possible manual placement or future balancing."
        )

    if metrics["underfilled_sessions"] > 0:
        recommendations.append(
            "Add availability or additional staff to improve coverage in underfilled sessions."
        )

    if coordinator_notes and coordinator_notes.strip():
        priorities_review.append(
            "Coordinator notes were included in this review and should be considered when assessing schedule quality."
        )

        note_text = coordinator_notes.lower()

        if "veteran" in note_text:
            if metrics["veteran_coverage_rate"] >= 80:
                strengths.append("The schedule aligns well with the stated veteran coverage priority.")
            else:
                tradeoffs.append("The schedule only partially satisfies the stated veteran coverage priority.")

        if "partner" in note_text:
            if metrics["partner_preference_matches"] > 0:
                strengths.append("The schedule satisfies some of the stated partner-related priorities.")
            else:
                tradeoffs.append("The schedule did not produce any partner preference matches despite partner-related priorities.")

        if "balance" in note_text or "workload" in note_text:
            recommendations.append("Review staff load distribution to confirm the workload is balanced across all assigned staff.")

    if not recommendations:
        recommendations.append(
            "This schedule is balanced overall and needs only minor manual review."
        )

    summary = (
        f"This schedule covers {metrics['coverage_rate']}% of sessions at minimum staffing levels, "
        f"with veteran coverage in {metrics['veteran_covered_sessions']} of {metrics['total_sessions']} sessions. "
        f"It includes {metrics['first_choice_matches']} first-choice matches, "
        f"{metrics['second_choice_matches']} second-choice matches, and "
        f"{metrics['partner_preference_matches']} partner preference match(es)."
    )

    return {
        "summary": summary,
        "priorities_review": priorities_review,
        "strengths": strengths,
        "tradeoffs": tradeoffs,
        "recommendations": recommendations,
    }

# -----------------------------------------------------------------------------
# API Models
# -----------------------------------------------------------------------------
class ScheduleRequest(BaseModel):
    course_rows: List[Dict[str, Any]] | None = None
    staff_rows: List[Dict[str, Any]] | None = None


class ExplainScheduleRequest(BaseModel):
    schedule_result: Dict[str, Any]
    staff_rows: List[Dict[str, Any]] | None = None
    coordinator_notes: str | None = None

# -----------------------------------------------------------------------------
# API: Upload Rosters
# -----------------------------------------------------------------------------
@app.post("/api/upload-rosters")
async def upload_rosters(
    course_roster: UploadFile = File(...),
    staff_roster: UploadFile = File(...),
):
    course_rows = _parse_csv_upload(course_roster)
    staff_rows = _parse_csv_upload(staff_roster)

    if not course_rows or not staff_rows:
        raise HTTPException(status_code=400, detail="One or both CSV files are empty.")

    def _check_headers(rows: List[Dict[str, Any]], required: List[str], label: str) -> None:
        got = {_normalize_header(k) for k in rows[0].keys()}
        missing = [c for c in required if _normalize_header(c) not in got]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"{label} missing columns: {', '.join(missing)}",
            )

    _check_headers(course_rows, COURSE_COLS, "Course")
    _check_headers(staff_rows, STAFF_COLS, "Staff")

    global LAST_COURSE_ROWS, LAST_STAFF_ROWS
    LAST_COURSE_ROWS = course_rows
    LAST_STAFF_ROWS = staff_rows

    return {
        "ok": True,
        "course_rows": len(course_rows),
        "staff_rows": len(staff_rows),
        "course_data": course_rows,
        "staff_data": staff_rows,
    }

# -----------------------------------------------------------------------------
# API: Generate Schedule
# -----------------------------------------------------------------------------
@app.post("/api/generate-schedule")
def api_generate_schedule(req: ScheduleRequest | None = Body(default=None)):
    req = req or ScheduleRequest()
    course_rows = req.course_rows or LAST_COURSE_ROWS
    staff_rows = req.staff_rows or LAST_STAFF_ROWS

    if not course_rows or not staff_rows:
        raise HTTPException(status_code=400, detail="No data uploaded.")

    return _generate_schedule(course_rows, staff_rows)


@app.post("/api/schedule-metrics")
def schedule_metrics(req: ScheduleRequest | None = Body(default=None)):
    req = req or ScheduleRequest()
    course_rows = req.course_rows or LAST_COURSE_ROWS
    staff_rows = req.staff_rows or LAST_STAFF_ROWS

    if not course_rows or not staff_rows:
        raise HTTPException(status_code=400, detail="No data uploaded.")

    schedule_result = _generate_schedule(course_rows, staff_rows)
    metrics = _compute_schedule_metrics(schedule_result, staff_rows)

    return {
        "schedule_result": schedule_result,
        "metrics": metrics,
    }


@app.post("/api/explain-schedule")
def explain_schedule(req: ExplainScheduleRequest):
    staff_rows = req.staff_rows or LAST_STAFF_ROWS

    if not req.schedule_result:
        raise HTTPException(status_code=400, detail="Missing schedule_result.")

    if not staff_rows:
        raise HTTPException(status_code=400, detail="Missing staff_rows.")

    metrics = _compute_schedule_metrics(req.schedule_result, staff_rows)
    explanation = _build_placeholder_explanation(
        req.schedule_result,
        metrics,
        req.coordinator_notes,
    )
    return {
        "metrics": metrics,
        "explanation": explanation,
    }

# -----------------------------------------------------------------------------
# Misc Endpoints
# -----------------------------------------------------------------------------
@app.post("/api/submit")
async def submit_schedule(request: Request):
    data = await request.json()
    return {"message": f"Schedule received for {data.get('taName')} on {data.get('days')}"}


@app.get("/api/health")
def health():
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# Serve Frontend
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend" / "dist"

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)