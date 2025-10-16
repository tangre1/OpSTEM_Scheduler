import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import Papa from "papaparse";

const C = { green: "#006747", dark: "#004c35", light: "#e6f2ee", accent: "#7fbf9f" };
const COURSE_COLS = ["Course", "Section", "Days", "StartTime", "EndTime", "Room"];
const STAFF_COLS  = ["Name", "Email", "Role", "Availability", "PreferredPartners"];

export default function CsuSchedulerDashboard() {
  const [courseFile, setCourseFile] = useState(null);
  const [staffFile,  setStaffFile]  = useState(null);
  const [courseRows, setCourseRows] = useState([]);
  const [staffRows,  setStaffRows]  = useState([]);
  const [toast,      setToast]      = useState("");
  const [error,      setError]      = useState("");

  // progress = 0/50/100 based on files present
  const progress = (courseFile ? 50 : 0) + (staffFile ? 50 : 0);

  async function parseCsv(file) {
    const text = await file.text();
    const { data } = Papa.parse(text, { header: true, skipEmptyLines: true });
    return data;
  }

  const courseMissing = useMemo(() => {
    if (!courseRows.length) return COURSE_COLS;
    const keys = new Set(Object.keys(courseRows[0] || {}));
    return COURSE_COLS.filter(k => !keys.has(k));
  }, [courseRows]);

  const staffMissing = useMemo(() => {
    if (!staffRows.length) return STAFF_COLS;
    const keys = new Set(Object.keys(staffRows[0] || {}));
    return STAFF_COLS.filter(k => !keys.has(k));
  }, [staffRows]);

  const handleFile = async (file, type) => {
    setError("");
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    if (ext !== "csv") { setError("Please upload a .csv file (use the template)."); return; }
    const rows = await parseCsv(file);
    if (type === "course") { setCourseFile(file); setCourseRows(rows); }
    else { setStaffFile(file); setStaffRows(rows); }
  };

  const onDrop = async (e, type) => {
    e.preventDefault(); e.stopPropagation();
    const f = e.dataTransfer?.files?.[0];
    if (f) await handleFile(f, type);
  };
  const onDrag = (e) => { e.preventDefault(); e.stopPropagation(); };

  const ready = progress === 100 && courseMissing.length === 0 && staffMissing.length === 0;

  const renderPreview = (rows) => {
    if (!rows.length) return <p className="text-gray-500 text-sm">No preview yet</p>;
    const headers = Array.from(new Set(rows.slice(0, 5).flatMap(r => Object.keys(r))));
    return (
      <div className="overflow-auto border rounded-xl mt-3">
        <table className="min-w-full text-sm">
          <thead>
            <tr>{headers.map(h => <th key={h} className="text-left p-2 border-b bg-gray-50 font-semibold">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.slice(0,5).map((r,i) => (
              <tr key={i} className="odd:bg-white even:bg-gray-50/40">
                {headers.map(h => <td key={h} className="p-2 border-b">{r[h] ?? ""}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const Card = ({title, file, rows, expect, onPick, onDropFile, templateName}) => (
    <motion.div
      className="bg-white rounded-3xl p-6 shadow border border-gray-100 h-full"
      whileHover={{ scale: 1.005 }}
    >
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-semibold" style={{ color: C.dark }}>{title}</h2>
        <span className="text-xs px-2 py-1 rounded-full border bg-gray-50 text-gray-700">CSV only</span>
      </div>

      <label
        onDragEnter={onDrag} onDragOver={onDrag} onDrop={onDropFile}
        className="block border-2 border-dashed border-gray-300 rounded-2xl p-8 text-center cursor-pointer hover:bg-[#f2fbf7] transition"
      >
        <input type="file" accept=".csv" className="hidden"
               onChange={(e) => e.target.files[0] && onPick(e.target.files[0])}/>
        {!file ? (
          <>
            <div className="mx-auto mb-3 w-12 h-12 rounded-xl grid place-items-center" style={{ background: C.light, color: C.green }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M19 20H5a2 2 0 0 1-2-2V8l4-4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2ZM5 8h14M9 3v5"/></svg>
            </div>
            <p className="text-gray-700">Drag & drop or click to upload</p>
            <p className="text-xs text-gray-500 mt-1">Use the template below</p>
          </>
        ) : (
          <>
            <p className="font-medium" style={{ color: C.green }}>{file.name}</p>
            <div className="mt-2 text-xs text-gray-600 flex gap-3">
              <span className="px-2 py-0.5 rounded-md bg-gray-100 border">Rows: <b>{rows.length}</b></span>
              <span className="px-2 py-0.5 rounded-md bg-gray-100 border">Cols: <b>{rows.length ? Object.keys(rows[0] || {}).length : 0}</b></span>
            </div>
            {renderPreview(rows)}
          </>
        )}
      </label>

      <p className="text-xs text-gray-600 mt-3">
        Expected columns: <span className="font-medium">{expect.join(", ")}</span>
      </p>

      <a
        href={URL.createObjectURL(new Blob([expect.join(",") + "\n"], { type: "text/csv" }))}
        download={templateName}
        className="inline-flex items-center gap-2 mt-3 px-3 py-2 rounded-xl border text-[13px] hover:bg-[#e6f2ee]"
        style={{ color: C.dark }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" className="opacity-80" fill="currentColor">
          <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Download Template
      </a>
    </motion.div>
  );

  const uploadRosters = async () => {
    if (!ready) return;
    setToast("Uploading…");
    const form = new FormData();
    form.append("course_roster", courseFile);
    form.append("staff_roster",  staffFile);
    try {
      const res = await fetch("/api/upload-rosters", { method: "POST", body: form });
      if (!res.ok) throw new Error();
      setToast("Uploaded! Redirecting…");
      setTimeout(() => (window.location.href = "/planner"), 800);
    } catch {
      setToast(""); setError("Upload failed — check files and try again.");
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: `linear-gradient(180deg, ${C.light}, #fff)` }}>
      {/* Top bar */}
      <header className="w-full bg-white/90 backdrop-blur border-b">
        <div className="w-full px-6 py-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl grid place-items-center font-bold text-white" style={{ background: C.green }}>CSU</div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold" style={{ color: C.dark }}>Scheduler Dashboard</h1>
            <p className="text-sm text-gray-600">Upload Course and Staff rosters to begin.</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 w-full px-6 py-8">
        {/* full-width, simple two-column grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card
            title="Course Roster"
            file={courseFile}
            rows={courseRows}
            expect={COURSE_COLS}
            onPick={(f) => handleFile(f, "course")}
            onDropFile={(e) => onDrop(e, "course")}
            templateName="course_roster_template.csv"
          />
          <Card
            title="Staff Roster"
            file={staffFile}
            rows={staffRows}
            expect={STAFF_COLS}
            onPick={(f) => handleFile(f, "staff")}
            onDropFile={(e) => onDrop(e, "staff")}
            templateName="staff_roster_template.csv"
          />
        </div>

        {error && (
          <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 text-amber-800 p-3 text-sm">
            {error}
          </div>
        )}
      </main>

      {/* Sticky bottom action bar */}
      <div className="w-full sticky bottom-0 left-0 bg-white/95 backdrop-blur border-t px-6 py-4">
        <div className="flex flex-col md:flex-row items-center gap-4">
          <div className="w-full">
            <div className="h-2 bg-gray-200 rounded-full">
              <motion.div
                className="h-2 rounded-full"
                animate={{ width: `${progress}%` }}
                style={{ background: C.accent }}
              />
            </div>
            <p className="text-xs text-gray-600 mt-1">
              {progress < 100
                ? "Upload both CSVs to continue."
                : (courseMissing.length || staffMissing.length)
                  ? "Fix missing columns before continuing."
                  : "Ready to continue."}
            </p>
          </div>
          <button
            onClick={uploadRosters}
            disabled={!ready}
            className={`px-6 py-3 rounded-2xl font-semibold transition ${
              !ready ? "bg-gray-300 text-gray-600 cursor-not-allowed" : "text-white hover:opacity-90"
            }`}
            style={{ background: ready ? C.green : undefined }}
          >
            Continue →
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-3 rounded-2xl shadow-lg text-white"
          style={{ background: C.dark }}
        >
          {toast}
        </motion.div>
      )}
    </div>
  );
}
