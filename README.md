# CSU Scheduler Dashboard

The CSU Scheduler Dashboard is a FastAPI-powered scheduling tool designed to automatically assign STEM Peer Teachers (SPTs) to math course sessions based on availability, preferences, and pairing rules.  
It ensures each course session is properly staffed with a balanced mix of veteran and new SPTs while keeping the process fair and efficient.

---

## Features

- Automatic scheduling of all SPTs based on course rosters and staff availability  
- Supports consistent CSU time blocks:
  - 9:10AM–11:05AM
  - 11:20AM–1:15PM
  - 1:30PM–2:20PM
- Ensures each session includes at least one veteran  
- Guarantees a minimum of two SPTs per group and caps at three maximum  
- Every SPT is scheduled somewhere (no one left unassigned)  
- Built-in balancing algorithm swaps veterans and new hires to maintain fairness  
- CSV upload support for course and staff rosters  
- Simple API endpoints for integration with a React or HTML frontend  

---

## Project Structure

CSU-Scheduler/
│
├── main.py # FastAPI backend logic (scheduler, upload, endpoints)
├── frontend/ # React or HTML UI directory (served statically)
│ └── index.html
│
├── course_roster_template.csv # Example course roster format
├── staff_roster_template.csv # Example staff roster format
│
└── README.md # This file

yaml
Copy code

---

## Requirements

Install Python dependencies:

```bash
pip install fastapi uvicorn python-multipart
If you’re running the frontend separately (like with Vite or React), you can still hit the backend API on port 8000.

Running the App
Start the server locally:

bash
Copy code
uvicorn main:app --reload
Then open your frontend or API tester at:

cpp
Copy code
http://127.0.0.1:8000
The backend serves /frontend statically by default.

CSV Format Guidelines
Course Roster (course_roster_template.csv)
Course	Section	Days	StartTime	EndTime	Room	Min # of SPTs Required
MTH 165	1	MWF	1:30PM	2:20PM	BH 429	2
MTH 167	1	MWF	9:10AM	10:00AM	BH 332	2

Times are automatically mapped into one of three SPT time blocks:

9:10–11:05 → Morning block

11:20–1:15 → Midday block

1:30–2:20 → Afternoon block

Staff Roster (staff_roster_template.csv)
Name:	Partner Preference 1:	Partner Preference 2:	Partner Preference 3:	1st Choice	2nd Choice	9:10AM-11:05AM	11:20AM-1:15PM	1:30PM-2:20PM	Veteran?
Asana Bostani	Caden			MTH 168	MTH 167	Y	Y	Y	Y
Azrael Manross	Racheal			MTH 181	MTH 182	Y	Y	Y	Y
Brandon Henderson	Mitchell	Racheal	Kyler	MTH 181	MTH 182	Y	Y	Y	Y

Availability columns accept “Y”, “Yes”, “True”, or “✓”.
“Veteran?” marks whether the SPT is experienced.

API Endpoints
POST /api/upload-rosters
Uploads the course and staff CSV files.

Request:

course_roster → file upload (CSV)

staff_roster → file upload (CSV)

Response:

json
Copy code
{
  "ok": true,
  "course_rows": 14,
  "staff_rows": 28
}
POST /api/generate-schedule
Generates the complete SPT schedule.

Request:

json
Copy code
{}
Response Example:

json
Copy code
{
  "assignments": {
    "9:10AM-11:05AM|MTH 167|1": {
      "meta": { "Course": "MTH 167", "Section": "1" },
      "assigned": [
        { "name": "Azrael Manross", "veteran": true },
        { "name": "Racheal Ina", "veteran": false }
      ]
    }
  },
  "staff_load": { "Azrael Manross": 1, "Racheal Ina": 1 }
}
GET /api/health
Returns a simple health check.

Response:

json
Copy code
{ "status": "ok" }
Scheduling Logic Overview
Rule	Description
At least 2 per session	Every class gets two SPTs minimum (if available).
At least 1 veteran	Each session must have one veteran. If two new hires are paired, a veteran is added or swapped in.
Max 3 total per session	Groups can expand to three only when unassigned staff remain.
Everyone placed	Every SPT is guaranteed a placement somewhere.
Balanced veterans	Veterans are distributed fairly across all time blocks.

How It Works
Rosters are parsed and normalized.

Staff are ranked using a scoring system that accounts for:

Course preferences (1st & 2nd choice)

Partner preferences

Veteran status

Sessions are populated in order of need.

The scheduler ensures all rules are met (2+ per session, veteran presence).

A final balancing pass redistributes veterans if any session lacks one.

Example Output Visualization
mathematica
Copy code
Total Staff: 28
All SPTs Assigned
0 Unbalanced Sessions
100% Sessions Have Veteran Coverage
Credits
Developed by Tanner Greene
Cleveland State University — Operation STEM Scheduler Project
Powered by FastAPI and Python 3.11

yaml
Copy code

---

Would you like me to add a short **Developer Setup** section at the bottom for integrating with your `CsuSchedulerDashboard.jsx` (React frontend)? It can include the API call examples for `/api/upload-rosters` and `/api/generate-schedule`.