// frontend/src/App.jsx
import React, { useState } from "react";
import CsuSchedulerDashboard from "./components/CsuSchedulerDashboard";
import ScheduleReview from "./components/ScheduleReview";
import "./index.css";

export default function App() {
  const [view, setView] = useState("upload");
  const [scheduleResult, setScheduleResult] = useState(null);
  const [staffRows, setStaffRows] = useState([]);

  return (
    <>
      {view === "upload" ? (
        <CsuSchedulerDashboard
          onScheduleGenerated={(result, staff) => {
            setScheduleResult(result);
            setStaffRows(staff || []);
            setView("review");
          }}
        />
      ) : (
        <ScheduleReview
          scheduleResult={scheduleResult}
          staffRows={staffRows}
          onBack={() => setView("upload")}
        />
      )}
    </>
  );
}