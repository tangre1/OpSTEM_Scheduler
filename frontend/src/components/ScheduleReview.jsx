import { useEffect, useState } from "react";

const THEME = {
  green: "#006747",
  dark: "#004C35",
  light: "#E6F2EE",
  grayBorder: "#E5E7EB",
  grayText: "#4B5563",
};

export default function ScheduleReview({
  scheduleResult,
  staffRows,
  notes,
  onBack,
}) {
  const [metrics, setMetrics] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError("");

        const res = await fetch("/api/explain-schedule", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            schedule_result: scheduleResult,
            staff_rows: staffRows,
            coordinator_notes: notes,
          }),
        });

        if (!res.ok) {
          throw new Error("Failed to explain schedule");
        }

        const data = await res.json();
        setMetrics(data.metrics);
        setExplanation(data.explanation);
      } catch (err) {
        setError("Could not analyze schedule.");
      } finally {
        setLoading(false);
      }
    };

    if (scheduleResult) {
      run();
    }
  }, [scheduleResult, staffRows, notes]);

  if (!scheduleResult) {
    return (
      <div style={{ padding: 24 }}>
        <p>No schedule available.</p>
        <button onClick={onBack}>Back</button>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #F6FBF8 0%, #FFFFFF 70%)",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 24,
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div>
            <h1
              style={{
                margin: 0,
                color: THEME.dark,
                fontFamily: "Merriweather, serif",
              }}
            >
              Schedule Review
            </h1>
            <p style={{ marginTop: 8, color: THEME.grayText }}>
              Review schedule quality, assignments, and explanation.
            </p>
          </div>

          <button
            onClick={onBack}
            style={{
              padding: "10px 16px",
              borderRadius: 12,
              border: `1px solid ${THEME.grayBorder}`,
              background: "#fff",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            ← Back
          </button>
        </div>

        {loading ? (
          <div style={panelStyle}>
            <p>Analyzing schedule...</p>
          </div>
        ) : (
          <>
            {error && (
              <div
                style={{
                  ...panelStyle,
                  border: "1px solid #FCD34D",
                  background: "#FFFBEB",
                }}
              >
                {error}
              </div>
            )}

            {metrics && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: 16,
                  marginBottom: 24,
                }}
              >
                <MetricCard
                  label="Coverage Rate"
                  value={`${metrics.coverage_rate}%`}
                />
                <MetricCard
                  label="Veteran Coverage"
                  value={`${metrics.veteran_coverage_rate}%`}
                />
                <MetricCard
                  label="First Choice Matches"
                  value={metrics.first_choice_matches}
                />
                <MetricCard
                  label="Second Choice Matches"
                  value={metrics.second_choice_matches}
                />
                <MetricCard
                  label="Partner Matches"
                  value={metrics.partner_preference_matches}
                />
                <MetricCard
                  label="Unassigned Staff"
                  value={metrics.unassigned_staff_count}
                />
              </div>
            )}

            {notes && notes.trim() && (
              <div style={panelStyle}>
                <h2 style={sectionTitle}>Coordinator Notes</h2>
                <p
                  style={{
                    color: THEME.grayText,
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                    marginBottom: 0,
                  }}
                >
                  {notes}
                </p>
              </div>
            )}

            {explanation && (
              <div style={panelStyle}>
                <h2 style={sectionTitle}>Schedule Explanation</h2>
                <p style={{ color: THEME.grayText, lineHeight: 1.6 }}>
                  {explanation.summary}
                </p>

                {explanation?.priorities_review?.length > 0 && (
                  <SectionList
                    title="Coordinator Priorities Review"
                    items={explanation.priorities_review}
                  />
                )}

                <SectionList title="Strengths" items={explanation.strengths} />
                <SectionList title="Tradeoffs" items={explanation.tradeoffs} />
                <SectionList
                  title="Recommendations"
                  items={explanation.recommendations}
                />
              </div>
            )}

            <div style={panelStyle}>
              <h2 style={sectionTitle}>Assignments</h2>
              <div style={{ display: "grid", gap: 16 }}>
                {Object.entries(scheduleResult.assignments || {}).map(
                  ([key, val]) => {
                    const [slot, course, section] = key.split("|");

                    return (
                      <div
                        key={key}
                        style={{
                          border: `1px solid ${THEME.grayBorder}`,
                          borderRadius: 12,
                          padding: 16,
                          background: "#fff",
                        }}
                      >
                        <h3 style={{ marginTop: 0, color: THEME.dark }}>
                          {course} — Section {section}
                        </h3>
                        <p style={{ color: THEME.grayText, marginTop: 0 }}>
                          {slot}
                        </p>

                        <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
                          {(val.assigned || []).map((a, i) => (
                            <li key={i} style={{ marginBottom: 6 }}>
                              {a.name} {a.veteran ? "⭐" : ""}
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  }
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #E5E7EB",
        borderRadius: 14,
        padding: 18,
      }}
    >
      <div style={{ fontSize: 13, color: "#4B5563", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: "#004C35" }}>
        {value}
      </div>
    </div>
  );
}

function SectionList({ title, items = [] }) {
  return (
    <div style={{ marginTop: 18 }}>
      <h3 style={{ marginBottom: 8 }}>{title}</h3>
      {items.length ? (
        <ul style={{ paddingLeft: 18, color: "#4B5563" }}>
          {items.map((item, i) => (
            <li key={`${title}-${i}`} style={{ marginBottom: 6 }}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ color: "#4B5563" }}>None.</p>
      )}
    </div>
  );
}

const panelStyle = {
  background: "#fff",
  border: "1px solid #E5E7EB",
  borderRadius: 16,
  padding: 20,
  marginBottom: 24,
  boxShadow: "0 6px 20px rgba(0,0,0,0.06)",
};

const sectionTitle = {
  marginTop: 0,
  color: "#004C35",
  fontFamily: "Merriweather, serif",
};