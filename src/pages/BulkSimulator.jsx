import { useState } from "react";
import { postBulkSimulate, postResetSimulate } from "../services/api";
import { C, cls } from "../styles";

const labelCls = cls.label;
const inputCls = cls.input;

export default function BulkSimulator() {
  const [form, setForm] = useState({
    customers: 5, months: 4, seed: 42,
    inject_time_shift: false,
    inject_amount_spike: false,
    inject_new_ip: false,
    output: "postgres",
  });
  const [response, setResponse] = useState(null);
  const [running, setRunning] = useState(false);
  const [resetting, setResetting] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((p) => ({ ...p, [name]: type === "checkbox" ? checked : value }));
  };

  const handleRun = async () => {
    setRunning(true);
    setResponse(null);
    const payload = {
      ...form,
      customers: parseInt(form.customers),
      months: parseInt(form.months),
      seed: parseInt(form.seed),
    };
    console.log("[FRMS] POST /simulate/bulk → payload:", payload);
    try {
      const { data } = await postBulkSimulate(payload);
      console.log("[FRMS] POST /simulate/bulk ← response:", data);
      setResponse(data);
    } catch (err) {
      const e = err?.response?.data || err.message;
      console.error("[FRMS] POST /simulate/bulk ← error:", e);
      setResponse({ error: e });
    } finally {
      setRunning(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm("⚠️ This will erase all simulation data from the database. Continue?")) return;
    setResetting(true);
    console.log("[FRMS] POST /simulate/reset →");
    try {
      const { data } = await postResetSimulate();
      console.log("[FRMS] POST /simulate/reset ← response:", data);
      setResponse(data);
    } catch (err) {
      const e = err?.response?.data || err.message;
      console.error("[FRMS] POST /simulate/reset ← error:", e);
      setResponse({ error: e });
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="min-h-screen flex font-sans" style={{ background: C.sand }}>

      {/* SIDEBAR */}
      <aside className="w-56 hidden lg:flex flex-col py-8 px-5 border-r shrink-0 sticky top-0 h-screen" style={{ background: C.navy, borderColor: "#243447" }}>
        <div className="mb-10 px-1">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: C.gold }}>
              <svg className="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm1 11H9v-2h2v2zm0-4H9V7h2v2z" />
              </svg>
            </div>
            <h1 className="text-base font-bold tracking-widest text-white uppercase">FRMS</h1>
          </div>
          <p className="text-[11px] pl-8" style={{ color: C.muted }}>Fraud Risk Monitoring</p>
        </div>
        <nav className="space-y-0.5">
          {[["Single Transaction", "/test"], ["Bulk Simulator", "/bulk"], ["Metrics", "/metrics"]].map(([label, href]) => {
            const active = window.location.pathname === href;
            return (
              <a key={label} href={href}
                className="w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2.5"
                style={active ? { background: "#243447", color: C.gold, borderLeft: `2px solid ${C.gold}` } : { color: C.muted, borderLeft: "2px solid transparent" }}
              >{label}</a>
            );
          })}
        </nav>
        <div className="mt-auto pt-5 border-t px-1" style={{ borderColor: "#243447" }}>
          <p className="text-[10px]" style={{ color: "#4A6080" }}>v1.0.0 · FRMS</p>
        </div>
      </aside>

      {/* MAIN */}
      <main className="flex-1 overflow-y-auto">
        <div className="sticky top-0 z-10 px-8 py-4 flex items-center justify-between border-b" style={{ background: C.sand, borderColor: C.border }}>
          <div>
            <h1 className="text-lg font-bold tracking-tight" style={{ color: C.text }}>Bulk Simulator</h1>
            <p className="text-xs mt-0.5" style={{ color: C.muted }}>Generate synthetic transaction data for testing</p>
          </div>
          <button
            onClick={handleReset}
            disabled={resetting}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-semibold transition-all"
            style={{ borderColor: C.red, color: C.red, background: C.white, opacity: resetting ? 0.6 : 1 }}
          >
            {resetting ? "Resetting..." : "Reset Data"}
          </button>
        </div>

        <div className="p-8 space-y-6">
          <div className="rounded-xl border overflow-hidden" style={{ background: C.white, borderColor: C.border }}>
            <div className="px-7 py-5 border-b" style={{ borderColor: C.border }}>
              <h2 className="text-sm font-bold uppercase tracking-widest" style={{ color: C.text }}>Simulation Parameters</h2>
              <p className="text-xs mt-0.5" style={{ color: C.muted }}>Configure synthetic data generation</p>
            </div>

            <div className="p-7 space-y-7">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
                {[["customers", "Customers"], ["months", "Months"], ["seed", "Random Seed"]].map(([key, label]) => (
                  <div key={key}>
                    <label className={labelCls}>{label}</label>
                    <input type="number" name={key} value={form[key]} onChange={handleChange} className={inputCls} />
                  </div>
                ))}
              </div>

              <div>
                <p className={labelCls + " mb-3"}>Anomaly Injections</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {[
                    ["inject_time_shift", "Time Shift"],
                    ["inject_amount_spike", "Amount Spike"],
                    ["inject_new_ip", "New IP"],
                  ].map(([key, label]) => (
                    <label key={key} className="flex items-center gap-3 p-4 rounded-lg border cursor-pointer transition-all"
                      style={{ borderColor: form[key] ? C.gold : C.border, background: form[key] ? "#FDF8F0" : C.white }}
                    >
                      <input type="checkbox" name={key} checked={form[key]} onChange={handleChange} className="w-4 h-4 accent-[#C8A96E]" />
                      <span className="text-sm font-medium" style={{ color: C.text }}>{label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t flex justify-end" style={{ borderColor: C.border }}>
                <button
                  onClick={handleRun}
                  disabled={running}
                  className="px-8 py-2.5 rounded-lg text-sm font-bold tracking-wide uppercase transition-all"
                  style={{ background: C.gold, color: C.white, opacity: running ? 0.75 : 1 }}
                  onMouseEnter={(e) => { if (!running) e.currentTarget.style.opacity = "0.88"; }}
                  onMouseLeave={(e) => { if (!running) e.currentTarget.style.opacity = "1"; }}
                >
                  {running ? "Running..." : "Run Simulation"}
                </button>
              </div>
            </div>
          </div>

          {/* RESPONSE */}
          <div className="rounded-xl border overflow-hidden" style={{ background: C.navy, borderColor: "#243447" }}>
            <div className="px-6 py-4 border-b flex items-center gap-2" style={{ borderColor: "#243447" }}>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke={C.gold} strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: C.muted }}>Simulation Result</h2>
            </div>
            <div className="p-6">
              {!response ? (
                <div className="rounded-lg p-8 text-center text-sm border border-dashed" style={{ borderColor: "#2D4A5E", color: "#4A6080" }}>
                  Run simulation to view results here.
                </div>
              ) : response.error ? (
                <div className="rounded-lg p-5 border" style={{ background: "#2A1A1E", borderColor: C.red }}>
                  <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: C.red }}>Error</p>
                  <p className="text-sm font-mono" style={{ color: "#F4A0A0" }}>
                    {typeof response.error === "object" ? JSON.stringify(response.error, null, 2) : response.error}
                  </p>
                </div>
              ) : (
                <div className="space-y-4">

                  {/* Summary cards */}
                  {response.summary && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {[
                        ["Customers", response.summary.customers],
                        ["Months", response.summary.months],
                        ["Total Transactions", response.summary.total_transactions],
                        ["Anomalous Transactions", response.summary.anomalous_transactions, true],
                      ].map(([label, val, warn]) => (
                        <div key={label} className="rounded-lg p-4 border" style={{ background: "#131F2B", borderColor: warn && val > 0 ? C.red : "#243447" }}>
                          <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: warn && val > 0 ? C.red : C.muted }}>{label}</p>
                          <p className="text-xl font-bold font-mono mt-1" style={{ color: warn && val > 0 ? "#F4A0A0" : "#E2C98A" }}>{val ?? "—"}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Anomaly flags */}
                  {response.summary && (
                    <div className="rounded-lg p-4 border" style={{ background: "#131F2B", borderColor: "#243447" }}>
                      <p className="text-[11px] font-bold uppercase tracking-widest mb-3" style={{ color: C.muted }}>Injected Anomalies</p>
                      <div className="flex flex-wrap gap-2">
                        {[["Time Shift", response.summary.inject_time_shift], ["Amount Spike", response.summary.inject_amount_spike], ["New IP", response.summary.inject_new_ip]].map(([label, active]) => (
                          <span key={label} className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide border"
                            style={active
                              ? { background: "#2A1A1E", borderColor: C.red, color: "#F4A0A0" }
                              : { background: "#162A1E", borderColor: C.green, color: "#86EFAC" }}
                          >
                            {active ? "⚠ " : "✓ "}{label}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Monthly scoring summary */}
                  {response.scoring_summary?.monthly_summary?.length > 0 && (
                    <div className="rounded-lg border overflow-hidden" style={{ borderColor: "#243447" }}>
                      <p className="px-4 py-3 text-[11px] font-bold uppercase tracking-widest border-b" style={{ background: "#1A2A38", borderColor: "#243447", color: C.muted }}>Monthly Scoring Summary</p>
                      <div className="divide-y" style={{ borderColor: "#243447" }}>
                        {response.scoring_summary.monthly_summary.map((m, i) => (
                          <div key={i} className="px-4 py-3 flex flex-wrap gap-x-6 gap-y-1" style={{ background: "#131F2B" }}>
                            <span className="text-xs font-mono" style={{ color: "#E2C98A" }}>{m.account_id} · {m.anomalous_month}</span>
                            <span className="text-xs" style={{ color: C.muted }}>txns: <span style={{ color: "#E2C98A" }}>{m.anomalous_month_txn_count}</span></span>
                            <span className="text-xs" style={{ color: C.muted }}>avg score: <span style={{ color: m.avg_behaviour_score > 0.5 ? "#F4A0A0" : "#86EFAC" }}>{(m.avg_behaviour_score * 100).toFixed(1)}%</span></span>
                            <span className="text-xs" style={{ color: C.muted }}>flagged: <span style={{ color: m.flagged_transactions > 0 ? "#F4A0A0" : "#86EFAC" }}>{m.flagged_transactions}</span></span>
                            {m.reasons?.length > 0 && (
                              <div className="flex gap-1 flex-wrap">
                                {m.reasons.map((r) => (
                                  <span key={r} className="px-2 py-0.5 rounded text-[10px] font-bold uppercase" style={{ background: "#2A1A1E", color: "#F4A0A0" }}>{r.replace(/_/g, " ")}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Raw JSON */}
                  <details className="rounded-lg border overflow-hidden" style={{ borderColor: "#243447" }}>
                    <summary className="px-4 py-2.5 text-xs font-bold uppercase tracking-widest cursor-pointer" style={{ background: "#1A2A38", color: C.muted }}>Raw JSON</summary>
                    <pre className="p-4 overflow-auto text-xs font-mono max-h-[400px]" style={{ background: "#131F2B", color: "#E2C98A" }}>
                      {JSON.stringify(response, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
