import { useEffect, useMemo, useRef, useState } from "react";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getAnalytics, getExplainability, getMeta, runPipelineAll, uploadWorkloadCsv } from "./api";

const PIE_COLORS = ["#8b5cf6", "#06b6d4", "#f59e0b", "#22c55e", "#ef4444"];
const toPercent = (value, total) => (total ? `${((value / total) * 100).toFixed(0)}%` : "0%");

function App() {
  const [currentPage, setCurrentPage] = useState("home");
  const [meta, setMeta] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [log, setLog] = useState("");
  const [explain, setExplain] = useState(null);
  const [activeModule, setActiveModule] = useState("executive");
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [savedViews, setSavedViews] = useState(() => JSON.parse(localStorage.getItem("dashboard_saved_views") || "[]"));
  const [viewName, setViewName] = useState("");
  const [runMode, setRunMode] = useState("demo");
  const [uploadFile, setUploadFile] = useState(null);
  const latestRequestRef = useRef(0);
  const captureRef = useRef(null);

  const [filters, setFilters] = useState({ decisions: [], regions: [], priorities: [] });

  const payload = useMemo(
    () => ({
      ...filters,
      logic: "and",
      limit: 300,
    }),
    [filters]
  );

  const safeInsights = useMemo(() => {
    const backendInsights = analytics?.insights || [];
    if (backendInsights.length > 0) return backendInsights;

    const total = analytics?.counts?.total ?? 0;
    const filtered = analytics?.counts?.filtered ?? 0;
    const reduction = meta?.kpis?.Total_Reduction;
    const reductionPct = meta?.kpis?.Reduction_Percentage;

    return [
      {
        title: "Matched Tasks",
        value: String(filtered),
        description: `Out of ${total} total tasks for current filters.`,
      },
      {
        title: "Overall Reduction",
        value: reduction !== undefined ? Number(reduction).toFixed(2) : "--",
        description: reductionPct !== undefined ? `${Number(reductionPct).toFixed(2)}% from summary output.` : "Summary not available.",
      },
      {
        title: "Insight Status",
        value: "Fallback",
        description: "Backend returned no insight cards; showing computed fallback insights.",
      },
    ];
  }, [analytics, meta]);

  async function loadMeta() {
    const m = await getMeta();
    setMeta(m);
  }

  async function loadAnalytics(currentPayload = payload) {
    const requestId = ++latestRequestRef.current;
    const data = await getAnalytics(currentPayload);
    const explainData = await getExplainability(currentPayload);
    // Ignore stale/out-of-order responses from rapid filter clicks.
    if (requestId === latestRequestRef.current) {
      setAnalytics(data);
      setExplain(explainData);
    }
  }

  async function refreshAll() {
    setLoading(true);
    setError("");
    try {
      await loadMeta();
      await loadAnalytics();
    } catch (e) {
      setError(e.message || "Unable to fetch data from backend");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setRunMode("demo");
    refreshAll();
  }, []);

  useEffect(() => {
    if (!meta) return;
    loadAnalytics(payload).catch((e) => setError(e.message || "Failed to update analytics"));
  }, [payload, meta]);

  async function handleRunAll() {
    setRunning(true);
    setLog("");
    try {
      const res = await runPipelineAll(runMode);
      setLog(res?.success ? `Pipeline executed successfully in ${runMode.toUpperCase()} mode.` : "Pipeline failed. Please retry.");
      await refreshAll();
    } catch (e) {
      setLog(e.message || "Pipeline failed. Please retry.");
    } finally {
      setRunning(false);
    }
  }

  async function handleUploadWorkload() {
    if (!uploadFile) {
      setLog("Choose a CSV file before uploading.");
      return;
    }
    try {
      const res = await uploadWorkloadCsv(uploadFile);
      setLog(`Upload successful: ${res.rows} rows validated.`);
      setRunMode("real");
    } catch (e) {
      setLog(e.message || "Upload failed.");
    }
  }

  function toggleFilter(key, value) {
    setFilters((prev) => {
      const current = prev[key];
      const exists = current.includes(value);
      return {
        ...prev,
        [key]: exists ? current.filter((x) => x !== value) : [...current, value],
      };
    });
  }

  function clearFilters() {
    setFilters({ decisions: [], regions: [], priorities: [] });
  }

  function scrollToPipelineFlow() {
    const section = document.getElementById("pipeline-flow");
    if (section) section.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function saveCurrentView() {
    const name = viewName.trim();
    if (!name) return;
    const entry = {
      id: `${Date.now()}`,
      name,
      filters,
      module: activeModule,
    };
    const updated = [...savedViews.filter((v) => v.name !== name), entry];
    setSavedViews(updated);
    localStorage.setItem("dashboard_saved_views", JSON.stringify(updated));
    setViewName("");
  }

  function loadView(view) {
    setFilters(view.filters || { decisions: [], regions: [], priorities: [] });
    setActiveModule(view.module || "executive");
  }

  function deleteView(id) {
    const updated = savedViews.filter((v) => v.id !== id);
    setSavedViews(updated);
    localStorage.setItem("dashboard_saved_views", JSON.stringify(updated));
  }

  async function exportOverallBoardPackPdf() {
    if (!captureRef.current || isExportingPdf) return;
    setIsExportingPdf(true);
    const previous = activeModule;
    const modules = ["executive", "insights", "operations", "xai", "pipeline"];
    const pdf = new jsPDF("l", "pt", "a4");
    let isFirstPage = true;
    try {
      for (const moduleKey of modules) {
        setActiveModule(moduleKey);
        // wait for module render
        await new Promise((r) => setTimeout(r, 450));
        const canvas = await html2canvas(captureRef.current, {
          scale: 2,
          backgroundColor: "#0b1220",
          useCORS: true,
        });
        const imgData = canvas.toDataURL("image/png");
        const pageWidth = pdf.internal.pageSize.getWidth();
        const pageHeight = pdf.internal.pageSize.getHeight();
        const imgRatio = canvas.width / canvas.height;
        let imgWidth = pageWidth - 30;
        let imgHeight = imgWidth / imgRatio;
        if (imgHeight > pageHeight - 30) {
          imgHeight = pageHeight - 30;
          imgWidth = imgHeight * imgRatio;
        }
        if (!isFirstPage) pdf.addPage();
        isFirstPage = false;
        pdf.addImage(imgData, "PNG", 15, 15, imgWidth, imgHeight);
      }
      pdf.save("carbon-dashboard-overall-board-pack.pdf");
    } catch (e) {
      setError(e.message || "Failed to export PDF.");
    } finally {
      setActiveModule(previous);
      setIsExportingPdf(false);
    }
  }

  if (loading) return <div className="center">Loading dashboard...</div>;

  return (
    <div className="app" ref={captureRef}>
      {currentPage === "home" ? (
        <section className="home-page">
          <div className="home-hero modern-hero">
            <div className="hero-left">
              <h1>Carbon Optimizer Platform</h1>
              <p className="hero-subtitle">Full-stack monitoring, scheduling insights, and carbon-aware optimization pipeline</p>
              <p>
                Leverage machine learning and intelligent scheduling to reduce carbon emissions across cloud workloads with
                real-time insights and explainable decisions.
              </p>
              <div className="home-actions">
                <button className="btn btn-primary home-btn" onClick={() => setCurrentPage("dashboard")}>
                  Open Dashboard
                </button>
                <button className="btn btn-soft home-btn" onClick={scrollToPipelineFlow}>
                  View Pipeline Flow
                </button>
              </div>
            </div>
            <div className="hero-right">
              <article className="preview-card">
                <h3>Live Dashboard Preview</h3>
                <div className="preview-kpis">
                  <div className="preview-kpi"><span>Total Predicted</span><strong>{meta?.kpis?.Total_Predicted_Carbon ? Number(meta.kpis.Total_Predicted_Carbon).toFixed(2) : "--"}</strong></div>
                  <div className="preview-kpi"><span>Reduction %</span><strong>{meta?.kpis?.Reduction_Percentage ? `${Number(meta.kpis.Reduction_Percentage).toFixed(2)}%` : "--"}</strong></div>
                  <div className="preview-kpi"><span>Optimized</span><strong>{meta?.kpis?.Total_Optimized_Carbon ? Number(meta.kpis.Total_Optimized_Carbon).toFixed(2) : "--"}</strong></div>
                </div>
                <div className="preview-chart">
                  <ResponsiveContainer width="100%" height={170}>
                    <BarChart data={(analytics?.charts?.carbonByDecision || []).slice(0, 4)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="name" hide />
                      <YAxis hide />
                      <Tooltip
                        formatter={(value) => [`Carbon: ${Number(value).toFixed(2)} units`, ""]}
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          border: "1px solid #334155",
                          borderRadius: "8px",
                        }}
                        labelStyle={{ color: "#e2e8f0", fontWeight: 700 }}
                        itemStyle={{ color: "#22c55e", fontWeight: 700 }}
                        cursor={{ fill: "rgba(148, 163, 184, 0.12)" }}
                      />
                      <Bar dataKey="optimized" fill="#22c55e" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </article>
            </div>
          </div>

          <div className="metric-strip">
            <div className="metric-pill">🌱 {meta?.kpis?.Reduction_Percentage ? `${Number(meta.kpis.Reduction_Percentage).toFixed(0)}%` : "--"} Carbon Reduction</div>
            <div className="metric-pill">⚙️ 96 Optimization Scenarios</div>
            <div className="metric-pill">📊 Real-time ML Predictions</div>
            <div className="metric-pill">🌍 Multi-region Scheduling</div>
          </div>

          <div className="home-cards">
            <article className="home-card">
              <h3>Executive Overview</h3>
              <p>KPI tracking and carbon reduction metrics for leadership visibility.</p>
            </article>
            <article className="home-card">
              <h3>Optimization Insights</h3>
              <p>Decision-level impact analysis with before/after carbon comparison.</p>
            </article>
            <article className="home-card">
              <h3>Operations Explorer</h3>
              <p>Task-level trends, segment filtering, and operational drill-down.</p>
            </article>
            <article className="home-card">
              <h3>Explainability AI</h3>
              <p>Human-readable insights, key drivers, and recommendation engine.</p>
            </article>
            <article className="home-card">
              <h3>Pipeline Ops</h3>
              <p>Run and monitor the end-to-end machine learning optimization pipeline with Demo and Real execution modes.</p>
            </article>
            <article className="home-card">
              <h3>Real Workload Mode</h3>
              <p>Upload actual workload CSV input, validate schema, and execute a real-run pipeline with production-like behavior.</p>
            </article>
            <article className="home-card">
              <h3>Board Pack Export</h3>
              <p>Generate PDF-ready stakeholder packs covering all enterprise modules in one overall report.</p>
            </article>
          </div>

          <section id="pipeline-flow" className="pipeline-flow">
            <h2>Pipeline Flow</h2>
            <div className="flow-track">
              {["Train Model", "Predict Emissions", "Decision Engine", "Scheduler", "Evaluation"].map((step, i) => (
                <div key={step} className="flow-node-wrap">
                  <div className="flow-node">{step}</div>
                  {i < 4 && <div className="flow-arrow">→</div>}
                </div>
              ))}
            </div>
          </section>
        </section>
      ) : (
        <>
      <header className="hero">
        <h1>Carbon Optimizer Platform</h1>
        <p>Full-stack monitoring, scheduling insights, and pipeline control</p>
        <div className="hero-actions">
          <button className="chip chip-on" onClick={() => setCurrentPage("home")}>Home</button>
        </div>
      </header>
      <nav className="module-nav">
        {[
          ["executive", "Executive Overview"],
          ["insights", "Optimization Insights"],
          ["operations", "Operations Explorer"],
          ["xai", "Explainability AI"],
          ["pipeline", "Pipeline Ops"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={activeModule === key ? "module-tab module-tab-on" : "module-tab"}
            onClick={() => setActiveModule(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {error && <div className="error">{error}</div>}

      <div className="layout">
        <aside className="sidebar">
          <section className="panel">
            <h3>Global Filters</h3>
            <p className="hint">
              AND logic across modules
            </p>
            <h4>Decision</h4>
            <div className="chip-wrap">
              {meta?.filters?.decisions?.map((d) => (
                <button key={d.value} className={filters.decisions.includes(d.value) ? "chip chip-on" : "chip"} onClick={() => toggleFilter("decisions", d.value)}>
                  {d.label}
                </button>
              ))}
            </div>
            <h4>Region</h4>
            <div className="chip-wrap">
              {meta?.filters?.regions?.map((r) => (
                <button key={r.value} className={filters.regions.includes(r.value) ? "chip chip-on" : "chip"} onClick={() => toggleFilter("regions", r.value)}>
                  {r.label}
                </button>
              ))}
            </div>
            <h4>Priority</h4>
            <div className="chip-wrap">
              {meta?.filters?.priorities?.map((p) => (
                <button key={p.value} className={filters.priorities.includes(p.value) ? "chip chip-on" : "chip"} onClick={() => toggleFilter("priorities", p.value)}>
                  {p.label}
                </button>
              ))}
            </div>
            <button className="btn btn-soft" onClick={clearFilters}>
              Clear Filters
            </button>
            <button className="btn btn-soft" onClick={exportOverallBoardPackPdf} disabled={isExportingPdf}>
              {isExportingPdf ? "Preparing PDF..." : "Download Overall Board Pack (PDF)"}
            </button>
          </section>
          <section className="panel">
            <h3>Saved Views</h3>
            <input
              className="view-input"
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              placeholder="Name this dashboard view"
            />
            <button className="btn btn-soft" onClick={saveCurrentView}>
              Save Current View
            </button>
            <div className="saved-view-list">
              {savedViews.map((v) => (
                <div key={v.id} className="saved-view-item">
                  <button className="chip chip-on" onClick={() => loadView(v)}>{v.name}</button>
                  <button className="chip" onClick={() => deleteView(v.id)}>Delete</button>
                </div>
              ))}
            </div>
          </section>
        </aside>

        <main className="content">
          {activeModule === "executive" && (
            <>
          <section className="kpis">
            <Kpi title="Total Predicted" value={meta?.kpis?.Total_Predicted_Carbon} />
            <Kpi title="Total Optimized" value={meta?.kpis?.Total_Optimized_Carbon} />
            <Kpi title="Total Reduction" value={meta?.kpis?.Total_Reduction} positive />
            <Kpi title="Reduction %" value={meta?.kpis?.Reduction_Percentage} suffix="%" positive />
            <Kpi title="Avg / Task" value={meta?.kpis?.Average_Reduction_Per_Task} />
          </section>

          <section className="insights">
            {safeInsights.map((x) => (
              <article key={x.title} className="insight-card">
                <h4>{x.title}</h4>
                <div className="insight-value">{x.value}</div>
                <p>{x.description}</p>
              </article>
            ))}
          </section>
          <p className="hint">
            You are currently viewing <b>{analytics?.counts?.filtered ?? 0}</b> tasks out of <b>{analytics?.counts?.total ?? 0}</b>.
          </p>

          <section className="charts two">
            <ChartCard title="How tasks are being handled (Decision Mix)">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={analytics?.charts?.decisionMix || []}
                    dataKey="count"
                    nameKey="name"
                    outerRadius={95}
                    label={({ count }) => toPercent(count, analytics?.counts?.filtered ?? 0)}
                  >
                    {(analytics?.charts?.decisionMix || []).map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, _name, item) => [`${value} tasks`, item?.payload?.name || "Decision"]} />
                </PieChart>
              </ResponsiveContainer>
              <PieTextLegend
                items={(analytics?.charts?.decisionMix || []).map((item, i) => ({
                  label: item.name || item.decision || item.Decision_Label || `Decision ${i + 1}`,
                  color: PIE_COLORS[i % PIE_COLORS.length],
                  count: item.count ?? 0,
                }))}
              />
            </ChartCard>

            <ChartCard title="Where tasks end up (Region Mix)">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={analytics?.charts?.regionMix || []}
                    dataKey="count"
                    nameKey="name"
                    outerRadius={95}
                    label={({ count }) => toPercent(count, analytics?.counts?.filtered ?? 0)}
                  >
                    {(analytics?.charts?.regionMix || []).map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[(i + 2) % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, _name, item) => [`${value} tasks`, item?.payload?.name || "Region"]} />
                </PieChart>
              </ResponsiveContainer>
              <PieTextLegend
                items={(analytics?.charts?.regionMix || []).map((item, i) => ({
                  label: item.name || item.region || item.Region_Label || `Region ${i + 1}`,
                  color: PIE_COLORS[(i + 2) % PIE_COLORS.length],
                  count: item.count ?? 0,
                }))}
              />
            </ChartCard>
          </section>
          </>
          )}

          {activeModule === "insights" && (
            <>
              <section className="insights">
                {safeInsights.map((x) => (
                  <article key={x.title} className="insight-card">
                    <h4>{x.title}</h4>
                    <div className="insight-value">{x.value}</div>
                    <p>{x.description}</p>
                  </article>
                ))}
              </section>
              <section className="charts two">
                <ChartCard title="Carbon before vs after optimization (by Decision)">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={analytics?.charts?.carbonByDecision || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="name" angle={-20} textAnchor="end" interval={0} height={80} />
                      <YAxis />
                      <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} units`, "Carbon"]} />
                      <Legend />
                      <Bar dataKey="predicted" name="Before optimization" fill="#f59e0b" />
                      <Bar dataKey="optimized" name="After optimization" fill="#22c55e" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
                <ChartCard title="Final carbon load by region">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={analytics?.charts?.carbonByRegion || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} units`, "Optimized carbon"]} />
                      <Bar dataKey="optimized" name="Optimized carbon" fill="#06b6d4" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
              </section>
            </>
          )}

          {activeModule === "operations" && (
            <section className="charts one">
              <ChartCard title="Task-level trend (Operational Explorer)">
                <ResponsiveContainer width="100%" height={380}>
                  <LineChart data={analytics?.charts?.trend || []}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="task" label={{ value: "Task Index", position: "insideBottom", offset: -5 }} />
                    <YAxis />
                    <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} units`, "Carbon"]} />
                    <Legend />
                    <Line type="monotone" name="Before optimization" dataKey="Predicted_Carbon_Emission" stroke="#f59e0b" strokeWidth={2} dot={false} />
                    <Line type="monotone" name="After optimization" dataKey="Optimized_Carbon_Emission" stroke="#22c55e" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
            </section>
          )}

          {activeModule === "xai" && (
            <section className="xai-grid">
              <article className="panel">
                <h3>Explainability AI Summary</h3>
                <p>{explain?.summary || "No explanation available."}</p>
                <p className="hint">Confidence risk level: <b>{explain?.risk_level || "unknown"}</b></p>
              </article>
              <article className="panel">
                <h3>What drives this insight</h3>
                <ul className="xai-list">
                  {(explain?.drivers || []).map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </article>
              <article className="panel">
                <h3>Recommended actions</h3>
                <ul className="xai-list">
                  {(explain?.recommendations || []).map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </article>
            </section>
          )}

          {activeModule === "pipeline" && (
            <section className="panel">
              <h3>Pipeline Operations</h3>
              <div className="run-mode-row">
                <button className={runMode === "demo" ? "chip chip-on" : "chip"} onClick={() => setRunMode("demo")}>
                  Demo Mode
                </button>
                <button className={runMode === "real" ? "chip chip-on" : "chip"} onClick={() => setRunMode("real")}>
                  Real Mode
                </button>
              </div>
              <p className="hint">
                Demo Mode enforces 96 coverage combos. Real Mode uses uploaded `new_incoming_workload.csv`.
              </p>
              <div className="upload-row">
                <input
                  type="file"
                  accept=".csv"
                  className="view-input"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
                <button className="btn btn-soft" onClick={handleUploadWorkload}>
                  Upload Workload CSV
                </button>
              </div>
              <button className="btn btn-primary" onClick={handleRunAll} disabled={running}>
                {running ? "Running..." : "Run Full Pipeline"}
              </button>
              <button className="btn btn-soft" onClick={refreshAll}>
                Refresh Data
              </button>
              {log && <textarea className="logs" value={log} readOnly />}
            </section>
          )}

          <section className="charts two">
            <ChartCard title="Carbon before vs after optimization (by Decision)">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={analytics?.charts?.carbonByDecision || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" angle={-20} textAnchor="end" interval={0} height={80} />
                  <YAxis />
                  <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} units`, "Carbon"]} />
                  <Legend />
                  <Bar dataKey="predicted" name="Before optimization" fill="#f59e0b" />
                  <Bar dataKey="optimized" name="After optimization" fill="#22c55e" />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Task-level trend (first 100 tasks)">
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={analytics?.charts?.trend || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="task" label={{ value: "Task Index", position: "insideBottom", offset: -5 }} />
                  <YAxis />
                  <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} units`, "Carbon"]} />
                  <Legend />
                  <Line type="monotone" name="Before optimization" dataKey="Predicted_Carbon_Emission" stroke="#f59e0b" strokeWidth={2} dot={false} />
                  <Line type="monotone" name="After optimization" dataKey="Optimized_Carbon_Emission" stroke="#22c55e" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          </section>

          <section className="charts one">
            <ChartCard title="Final carbon load by region (after optimization)">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={analytics?.charts?.carbonByRegion || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(value) => [`${Number(value).toFixed(2)} units`, "Optimized carbon"]} />
                  <Bar dataKey="optimized" name="Optimized carbon" fill="#06b6d4" />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </section>
        </main>
      </div>
      </>
      )}
    </div>
  );
}

function Kpi({ title, value, suffix = "", positive = false }) {
  const formatted = typeof value === "number" ? value.toFixed(2) : value ?? "--";
  return (
    <article className="kpi">
      <h4>{title}</h4>
      <div className={positive ? "kpi-value positive" : "kpi-value"}>
        {formatted}
        {suffix}
      </div>
    </article>
  );
}

function ChartCard({ title, children }) {
  return (
    <article className="chart-card">
      <h3>{title}</h3>
      {children}
    </article>
  );
}

function PieTextLegend({ items }) {
  if (!items?.length) return null;
  return (
    <div className="pie-legend">
      {items.map((item) => (
        <div key={`${item.label}-${item.count}`} className="pie-legend-item">
          <span className="pie-legend-dot" style={{ backgroundColor: item.color }} />
          <span className="pie-legend-text">
            {item.label} ({item.count})
          </span>
        </div>
      ))}
    </div>
  );
}

export default App;
