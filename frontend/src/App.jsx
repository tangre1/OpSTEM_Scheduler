// frontend/src/App.jsx
import React, { useState } from "react";
import CsuSchedulerDashboard from "./components/CsuSchedulerDashboard";
import ScheduleReview from "./components/ScheduleReview";
import "./index.css";

export default function App() {
  const [view, setView] = useState("upload");
  const [scheduleResult, setScheduleResult] = useState(null);
  const [staffRows, setStaffRows] = useState([]);
  const [notes, setNotes] = useState("");

  return (
    <>
      {view === "upload" ? (
        <CsuSchedulerDashboard
          onScheduleGenerated={(result, staff, notesInput) => {
            setScheduleResult(result);
            setStaffRows(staff || []);
            setNotes(notesInput || "");
            setView("review");
          }}
        />
      ) : (
        <ScheduleReview
          scheduleResult={scheduleResult}
          staffRows={staffRows}
          notes={notes}
          onBack={() => setView("upload")}
        />
      )}
    </>
  );
}