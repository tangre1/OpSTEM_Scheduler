import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import Papa from "papaparse";

/**
 * CSU-inspired theme (Cleveland State University)
 * Colors sourced from their typical brand palette:
 * - Viking Green (primary): #006747
 * - Dark Green (headers):   #004C35
 * - Light Tint              #E6F2EE
 * - Accent                  #7FBF9F
 */
const THEME = {
  green: "#006747",
  dark: "#004C35",
  light: "#E6F2EE",
  accent: "#7FBF9F",
  grayText: "#4B5563",
  grayBorder: "#E5E7EB",
  cardShadow: "0 6px 20px rgba(0,0,0,0.08)",
  cardShadowHover: "0 10px 28px rgba(0,0,0,0.12)"
};

const COURSE_COLS = ["Course", "Section", "Days", "StartTime", "EndTime", "Room"];
const STAFF_COLS  = ["Name", "Email", "Role", "Availability", "PreferredPartners"];

export default function CsuSchedulerDashboard() {
  // Inject fonts
  useEffect(() => {
    const link1 = document.createElement("link");
    link1.rel = "preconnect";
    link1.href = "https://fonts.googleapis.com";
    const link2 = document.createElement("link");
    link2.rel = "preconnect";
    link2.href = "https://fonts.gstatic.com";
    link2.crossOrigin = "anonymous";
    const link3 = document.createElement("link");
    link3.href =
      "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Merriweather:wght@700;900&display=swap";
    link3.rel = "stylesheet";
    document.head.append(link1, link2, link3);
    return () => { link1.remove(); link2.remove(); link3.remove(); };
  }, []);

  const [courseFile, setCourseFile] = useState(null);
  const [staffFile,  setStaffFile]  = useState(null);
  const [courseRows, setCourseRows] = useState([]);
  const [staffRows,  setStaffRows]  = useState([]);
  const [toast,      setToast]      = useState("");
  const [error,      setError]      = useState("");

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
    if (ext !== "csv") {
      setError("Please upload a .csv file (use the provided template).");
      return;
    }
    const rows = await parseCsv(file);
    if (type === "course") { setCourseFile(file); setCourseRows(rows); }
    else { setStaffFile(file); setStaffRows(rows); }
  };

  const onDrop = async (e, type) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f) await handleFile(f, type);
  };

  const ready =
    progress === 100 &&
    courseMissing.length === 0 &&
    staffMissing.length === 0;

  const renderPreview = (rows) => {
    if (!rows.length) {
      return <p style={{color:"#6B7280", fontSize:12, textAlign:"center", marginTop:10}}>No preview yet</p>;
    }
    const headers = Array.from(new Set(rows.slice(0,5).flatMap(r => Object.keys(r))));
    return (
      <div style={{
        border: `1px solid ${THEME.grayBorder}`,
        borderRadius: 12,
        marginTop: 12
      }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:14 }}>
          <thead>
            <tr>
              {headers.map(h => (
                <th key={h} style={{
                  textAlign:"left",
                  padding:"10px 12px",
                  borderBottom:`1px solid ${THEME.grayBorder}`,
                  background:"#F9FAFB",
                  fontWeight:600
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0,5).map((r, i) => (
              <tr key={i} style={{ background: i%2 ? "rgba(0,0,0,0.02)" : "white" }}>
                {headers.map(h => (
                  <td key={h} style={{
                    padding:"10px 12px",
                    borderBottom:`1px solid ${THEME.grayBorder}`
                  }}>{r[h] ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const UploadCard = ({ title, file, rows, expect, onPick, onDropFile, templateName }) => {
    const inputRef = useRef(null);

    const card = {
      background: "#fff",
      border: `1px solid ${THEME.grayBorder}`,
      borderRadius: 20,
      padding: 24,
      boxShadow: THEME.cardShadow,
      willChange: "box-shadow",
      backfaceVisibility: "hidden"
    };

    const pickerBox = {
      border: `1px solid ${THEME.grayBorder}`,
      borderRadius: 16,
      padding: 28,
      textAlign: "center",
      background: "#F7FAF7",
      cursor: "pointer",
      transition: "background .2s ease"
    };

    return (
      <div
        style={{ ...card, transition: "box-shadow 0.2s ease" }}
        onMouseEnter={e => (e.currentTarget.style.boxShadow = THEME.cardShadowHover)}
        onMouseLeave={e => (e.currentTarget.style.boxShadow = THEME.cardShadow)}
      >
        <div style={{display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:8}}>
          <h2 style={{fontFamily:"Merriweather, serif", fontSize:20, color:THEME.dark, margin:0}}>
            {title}
          </h2>
          <span style={{
            fontSize:11, padding:"4px 8px", border:`1px solid ${THEME.grayBorder}`,
            borderRadius:6, background:"#F3F4F6", color:"#374151"
          }}>CSV</span>
        </div>

        {/* Clickable upload area (no <label>) */}
        <div
          role="button"
          tabIndex={0}
          style={pickerBox}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
          onDragEnter={(e) => e.preventDefault()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDropFile}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#EEF7F1")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "#F7FAF7")}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            style={{ display:"none" }}
            onChange={(e) => e.target.files[0] && onPick(e.target.files[0])}
          />

          {!file ? (
            <>
              <div style={{
                width:44, height:44, margin:"0 auto 8px",
                borderRadius:10, display:"grid", placeItems:"center",
                background: THEME.light, color: THEME.green
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 20H5a2 2 0 0 1-2-2V8l4-4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2ZM5 8h14M9 3v5" />
                </svg>
              </div>
              <div style={{color:"#111827", fontWeight:600}}>Drag & drop or click to upload</div>
              <div style={{fontSize:12, color:"#6B7280", marginTop:4}}>Use the template below</div>
            </>
          ) : (
            <>
              <div style={{color:THEME.green, fontWeight:600}}>{file.name}</div>
              <div style={{marginTop:8, display:"flex", gap:8, justifyContent:"center", fontSize:12, color:"#6B7280"}}>
                <span style={{background:"#F3F4F6", border:"1px solid #E5E7EB", borderRadius:6, padding:"2px 8px"}}>
                  Rows: <b>{rows.length}</b>
                </span>
                <span style={{background:"#F3F4F6", border:"1px solid #E5E7EB", borderRadius:6, padding:"2px 8px"}}>
                  Cols: <b>{rows.length ? Object.keys(rows[0] || {}).length : 0}</b>
                </span>
              </div>
              {renderPreview(rows)}
            </>
          )}
        </div>

        <p style={{fontSize:12, color:"#6B7280", marginTop:12}}>
          Expected columns: <span style={{fontWeight:600, color:"#374151"}}>{expect.join(", ")}</span>
        </p>

        <div style={{display:"flex", justifyContent:"center"}}>
          <a
            href={URL.createObjectURL(new Blob([expect.join(",") + "\n"], { type: "text/csv" }))}
            download={templateName}
            style={{
              display:"inline-flex", alignItems:"center", gap:8,
              padding:"8px 12px", border:`1px solid ${THEME.grayBorder}`,
              borderRadius:12, fontSize:13, color:THEME.dark,
              background:"#FFFFFF", textDecoration:"none"
            }}
            onMouseEnter={e => (e.currentTarget.style.background = THEME.light)}
            onMouseLeave={e => (e.currentTarget.style.background = "#FFFFFF")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style={{opacity:.8}}>
              <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Download Template
          </a>
        </div>
      </div>
    );
  };

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
    <div style={{minHeight:"100vh", display:"flex", flexDirection:"column", background:"linear-gradient(180deg, #F6FBF8 0%, #FFFFFF 70%)"}}>
      {/* ============== CSU MASTHEAD ============== */}
      <style>{`
        :root { --csu-green:${THEME.green}; --csu-dark:${THEME.dark}; }
        .csu-masthead { background: var(--csu-green); color: #fff; }
        .csu-subbar   { background: #0f7a59; color:#d6faea; }
        .csu-container { width: 100%; max-width: 1120px; margin-inline: auto; padding-inline: 20px; }
        .csu-title { font-family: Merriweather, serif; font-weight: 900; letter-spacing: .2px; }
        .csu-body  { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }
        @media (max-width: 640px){ .csu-title{ font-size: 24px !important; } }
      `}</style>

      <header className="csu-body">
        <div className="csu-masthead">
          <div className="csu-container" style={{display:"flex", alignItems:"center", gap:14, padding:"12px 20px"}}>
            <div style={{
              width:36, height:36, borderRadius:"50%", background:"#fff",
              color:THEME.green, display:"grid", placeItems:"center", fontWeight:800
            }}>CSU</div>
            <div style={{lineHeight:1}}>
              <div style={{fontSize:14, opacity:.9}}>Cleveland State University</div>
              <div className="csu-title" style={{fontSize:28, marginTop:2}}>Scheduler Dashboard</div>
            </div>
          </div>
        </div>
        <div className="csu-subbar">
          <div className="csu-container" style={{padding:"6px 20px", fontSize:13}}>
            Upload Course and Staff rosters to begin.
          </div>
        </div>
      </header>

      {/* ============== MAIN ============== */}
      <main className="csu-body" style={{ flex:1, display:"flex", justifyContent:"center", padding:"40px 20px" }}>
        <div style={{ width:"100%", maxWidth: 980 }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap: 24 }}>
            <UploadCard
              title="Course Roster"
              file={courseFile}
              rows={courseRows}
              expect={COURSE_COLS}
              onPick={(f) => handleFile(f, "course")}
              onDropFile={(e) => onDrop(e, "course")}
              templateName="course_roster_template.csv"
            />
            <UploadCard
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
            <div style={{
              marginTop:16, border:`1px solid #FCD34D`, background:"#FFFBEB",
              color:"#92400E", borderRadius:14, padding:"10px 14px", fontSize:14
            }}>
              {error}
            </div>
          )}
        </div>
      </main>

      {/* ============== STICKY FOOTER ============== */}
      <footer className="csu-body" style={{
        position:"sticky", bottom:0, background:"#ffffffcc", backdropFilter:"blur(6px)",
        borderTop:`1px solid ${THEME.grayBorder}`
      }}>
        <div className="csu-container" style={{ display:"flex", alignItems:"center", gap:16, padding:"14px 20px" }}>
          <div style={{flex:1}}>
            <div style={{height:8, background:"#E5E7EB", borderRadius:999, overflow:"hidden"}}>
              <motion.div
                initial={false}
                animate={{ width: `${progress}%` }}
                style={{ height:"100%", background:`linear-gradient(90deg, ${THEME.green}, ${THEME.accent})` }}
              />
            </div>
            <div style={{fontSize:12, color:"#6B7280", marginTop:6}}>
              {progress < 100
                ? "Upload both CSVs to continue."
                : (courseMissing.length || staffMissing.length)
                  ? "Fix missing columns before continuing."
                  : "Ready to continue."}
            </div>
          </div>

          <button
            onClick={uploadRosters}
            disabled={!ready}
            style={{
              padding:"10px 18px", border:"none",
              borderRadius:14, fontWeight:700,
              background: ready ? THEME.green : "#D1D5DB",
              color: ready ? "#fff" : "#6B7280",
              cursor: ready ? "pointer" : "not-allowed",
              transform: "translateZ(0)"
            }}
            onMouseDown={e => ready && (e.currentTarget.style.transform = "scale(.98)")}
            onMouseUp={e => ready && (e.currentTarget.style.transform = "scale(1)")}
          >
            Continue →
          </button>
        </div>
      </footer>

      {/* Toast */}
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            position:"fixed", left:"50%", bottom:24, transform:"translateX(-50%)",
            background: THEME.dark, color:"#fff", padding:"10px 14px",
            borderRadius:14, boxShadow:"0 10px 24px rgba(0,0,0,0.15)", fontWeight:600
          }}
        >
          {toast}
        </motion.div>
      )}
    </div>
  );
}
