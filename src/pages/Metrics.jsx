import { useState } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Label,
} from "recharts";
import {
  postMetricsSummary,
  postProfileRetrieve,
  postTxnHistory,
  postScoringResults,
} from "../services/api";

import { C, cls, CHART_COLORS } from "../styles";

const labelCls = cls.label;
const inputCls = cls.input;

const axisStyle = { fontSize: 11, fill: C.muted };
const axisLabelStyle = { fontSize: 11, fill: C.muted };

function Paginator({ page, total, onChange }) {
  if (total <= 1) return null;
  return (
    <div className="flex items-center gap-2">
      <button onClick={() => onChange(Math.max(0, page - 1))} disabled={page === 0}
        className="px-2 py-1 text-xs rounded border" style={{ borderColor: C.border, color: page === 0 ? C.muted : C.text }}>←</button>
      <span className="text-xs" style={{ color: C.muted }}>{page + 1} / {total}</span>
      <button onClick={() => onChange(Math.min(total - 1, page + 1))} disabled={page === total - 1}
        className="px-2 py-1 text-xs rounded border" style={{ borderColor: C.border, color: page === total - 1 ? C.muted : C.text }}>→</button>
    </div>
  );
}

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-xl p-5 border" style={{ background: C.white, borderColor: C.border }}>
      <p className={labelCls}>{label}</p>
      <h2 className="text-xl font-bold mt-1" style={{ color: C.text }}>{value ?? "—"}</h2>
      {sub && <p className="text-xs mt-0.5" style={{ color: C.muted }}>{sub}</p>}
    </div>
  );
}

const PAGE_SIZE = 30;

export default function Metrics() {
  const [accountId, setAccountId] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [scorePage, setScorePage] = useState(0);
  const [amountPage, setAmountPage] = useState(0);

  const fetchAll = async () => {
    if (!accountId.trim()) return;
    setLoading(true);
    setData(null);
    setError(null);
    setScorePage(0);
    setAmountPage(0);
    console.log("[FRMS] Fetching metrics for:", accountId);
    try {
      const [summary, profile, history, scoring] = await Promise.all([
        postMetricsSummary(accountId),
        postProfileRetrieve(accountId),
        postTxnHistory(accountId),
        postScoringResults(accountId),
      ]);
      const result = {
        summary: summary.data,
        profile: profile.data.profile,
        transactions: history.data.transactions,
        scoring: scoring.data.scoring_results,
      };
      console.log("[FRMS] Metrics loaded:", result);
      setData(result);
    } catch (err) {
      const e = err?.response?.data || err.message;
      console.error("[FRMS] Metrics error:", e);
      setError(e);
    } finally {
      setLoading(false);
    }
  };

  // ── Chart data ────────────────────────────────────────────────────────────
  const scoringAll = data?.scoring?.map((r, i) => ({
    txn: `#${i + 1}`,
    score: parseFloat((r.behaviour_score * 100).toFixed(2)),
    date: r.event_ts?.slice(0, 10) ?? "",
  })) ?? [];

  const txnAll = data?.transactions?.map((t, i) => ({
    txn: `#${i + 1}`,
    amount: t.amount,
    date: t.event_ts?.slice(0, 10) ?? "",
  })) ?? [];

  const reasonData = data?.summary?.reason_counts?.map((r) => ({
    name: r.reason.replace(/_/g, " "),
    value: r.count,
  })) ?? [];

  const activeHoursData = (() => {
    const hours = Array.from({ length: 24 }, (_, h) => ({
      hour: `${String(h).padStart(2, "0")}:00`,
      count: 0,
    }));
    data?.profile?.active_hours?.forEach((h) => {
      if (hours[h]) hours[h].count += 1;
    });
    return hours;
  })();

  // Pagination slices
  const scorePages  = Math.max(1, Math.ceil(scoringAll.length / PAGE_SIZE));
  const scoreSlice  = scoringAll.slice(scorePage * PAGE_SIZE, (scorePage + 1) * PAGE_SIZE);
  const amountPages = Math.max(1, Math.ceil(txnAll.length / PAGE_SIZE));
  const amountSlice = txnAll.slice(amountPage * PAGE_SIZE, (amountPage + 1) * PAGE_SIZE);

  // Dynamic heights — min 200, scale with data, cap at 420
  const scoreH  = Math.min(Math.max(200, scoreSlice.length * 6), 420);
  const amountH = Math.min(Math.max(200, amountSlice.length * 8), 420);
  const reasonH = Math.min(Math.max(200, reasonData.length * 70), 340);

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
                className="w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center"
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
            <h1 className="text-lg font-bold tracking-tight" style={{ color: C.text }}>Metrics</h1>
            <p className="text-xs mt-0.5" style={{ color: C.muted }}>Account-level behavioural analytics</p>
          </div>
        </div>

        <div className="p-8 space-y-6">

          {/* ACCOUNT SEARCH */}
          <div className="rounded-xl border p-6 flex gap-4 items-end" style={{ background: C.white, borderColor: C.border }}>
            <div className="flex-1">
              <label className={labelCls}>Account ID</label>
              <input type="text" value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && fetchAll()}
                placeholder="e.g. ACC1000001" className={inputCls} />
            </div>
            <button onClick={fetchAll} disabled={loading || !accountId.trim()}
              className="px-8 py-2.5 rounded-lg text-sm font-bold tracking-wide uppercase transition-all"
              style={{ background: C.gold, color: C.white, opacity: loading ? 0.75 : 1 }}
              onMouseEnter={(e) => { if (!loading) e.currentTarget.style.opacity = "0.88"; }}
              onMouseLeave={(e) => { if (!loading) e.currentTarget.style.opacity = "1"; }}
            >{loading ? "Loading..." : "Load Metrics"}</button>
          </div>

          {error && (
            <div className="rounded-xl border p-5 text-sm" style={{ background: "#FFF5F5", borderColor: C.red, color: C.red }}>
              {typeof error === "object" ? JSON.stringify(error) : error}
            </div>
          )}

          {data && (
            <>
              {/* STAT CARDS */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard label="Total Transactions" value={data.summary?.summary?.total_transactions} />
                <StatCard label="Flagged" value={data.summary?.summary?.flagged_transactions} />
                <StatCard label="Avg Amount" value={data.summary?.summary?.average_amount != null ? `₹${Number(data.summary.summary.average_amount).toLocaleString()}` : "—"} />
                <StatCard label="Avg Behaviour Score" value={data.summary?.summary?.average_behaviour_score != null ? (data.summary.summary.average_behaviour_score * 100).toFixed(1) + "%" : "—"} />
              </div>

              {/* ROW 1 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* Behaviour Score Over Time */}
                <div className="rounded-xl border p-6" style={{ background: C.white, borderColor: C.border }}>
                  <div className="flex items-center justify-between mb-4">
                    <p className={labelCls}>Behaviour Score Over Time</p>
                    <Paginator page={scorePage} total={scorePages} onChange={setScorePage} />
                  </div>
                  <ResponsiveContainer width="100%" height={scoreH}>
                    <LineChart data={scoreSlice} margin={{ bottom: 30, left: 10, right: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                      <XAxis dataKey="txn" tick={axisStyle}>
                        <Label value="Transaction" offset={-20} position="insideBottom" style={axisLabelStyle} />
                      </XAxis>
                      <YAxis domain={[0, 100]} tick={axisStyle} unit="%">
                        <Label value="Score (%)" angle={-90} position="insideLeft" offset={10} style={axisLabelStyle} />
                      </YAxis>
                      <Tooltip formatter={(v, n, p) => [`${v}%`, "Score"]} labelFormatter={(l, items) => `${l} · ${items?.[0]?.payload?.date ?? ""}`} />
                      <Line type="monotone" dataKey="score" stroke={C.gold} strokeWidth={2} dot={scoreSlice.length < 20} activeDot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Transaction Amounts */}
                <div className="rounded-xl border p-6" style={{ background: C.white, borderColor: C.border }}>
                  <div className="flex items-center justify-between mb-4">
                    <p className={labelCls}>Transaction Amounts ({txnAll.length} total)</p>
                    <Paginator page={amountPage} total={amountPages} onChange={setAmountPage} />
                  </div>
                  <ResponsiveContainer width="100%" height={amountH}>
                    <BarChart data={amountSlice} margin={{ bottom: 30, left: 10, right: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                      <XAxis dataKey="txn" tick={axisStyle}>
                        <Label value="Transaction" offset={-20} position="insideBottom" style={axisLabelStyle} />
                      </XAxis>
                      <YAxis tick={axisStyle}>
                        <Label value="Amount (₹)" angle={-90} position="insideLeft" offset={10} style={axisLabelStyle} />
                      </YAxis>
                      <Tooltip formatter={(v) => [`₹${Number(v).toLocaleString()}`, "Amount"]} labelFormatter={(l, items) => `${l} · ${items?.[0]?.payload?.date ?? ""}`} />
                      <Bar dataKey="amount" fill={C.gold} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* ROW 2 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* Reason Breakdown */}
                <div className="rounded-xl border p-6" style={{ background: C.white, borderColor: C.border }}>
                  <p className={labelCls + " mb-4"}>Anomaly Reason Breakdown</p>
                  {reasonData.length === 0 ? (
                    <div className="flex items-center justify-center h-[200px] text-sm" style={{ color: C.muted }}>No anomaly reasons found</div>
                  ) : (
                    <div className="flex flex-col gap-4">
                      <ResponsiveContainer width="100%" height={200}>
                        <PieChart>
                          <Pie
                            data={reasonData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%" cy="50%"
                            innerRadius={55}
                            outerRadius={85}
                            paddingAngle={3}
                          >
                            {reasonData.map((_, i) => (
                              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip formatter={(v, n) => [v, n]} />
                        </PieChart>
                      </ResponsiveContainer>
                      {/* Legend below chart */}
                      <div className="flex flex-col gap-2">
                        {reasonData.map((r, i) => {
                          const total = reasonData.reduce((s, x) => s + x.value, 0);
                          const pct = ((r.value / total) * 100).toFixed(1);
                          return (
                            <div key={r.name} className="flex items-center gap-3">
                              <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                              <span className="text-xs flex-1 font-medium" style={{ color: C.text }}>{r.name}</span>
                              <span className="text-xs font-mono" style={{ color: C.muted }}>{r.value} <span style={{ color: C.text }}>({pct}%)</span></span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Active Hours */}
                <div className="rounded-xl border p-6" style={{ background: C.white, borderColor: C.border }}>
                  <p className={labelCls + " mb-4"}>Transaction Activity by Hour of Day</p>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={activeHoursData} margin={{ bottom: 36, left: 10, right: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                      <XAxis dataKey="hour" tick={{ fontSize: 9, fill: C.muted }} interval={0} angle={-45} textAnchor="end" height={50}>
                        <Label value="Hour of Day" offset={-30} position="insideBottom" style={axisLabelStyle} />
                      </XAxis>
                      <YAxis allowDecimals={false} tick={axisStyle}>
                        <Label value="Transactions" angle={-90} position="insideLeft" offset={10} style={axisLabelStyle} />
                      </YAxis>
                      <Tooltip formatter={(v) => [`${v} txn(s)`, "Count"]} />
                      <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                        {activeHoursData.map((entry, i) => (
                          <Cell key={i} fill={entry.count > 0 ? C.gold : C.border} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* PROFILE CARD */}
              {data.profile && (
                <div className="rounded-xl border p-6" style={{ background: C.white, borderColor: C.border }}>
                  <p className={labelCls + " mb-4"}>Behavioural Profile</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Avg Amount" value={`₹${Number(data.profile.avg_amount).toLocaleString()}`} />
                    <StatCard label="Std Dev Amount" value={`₹${Number(data.profile.std_amount).toLocaleString()}`} />
                    <StatCard label="Txn Frequency" value={data.profile.txn_frequency?.toFixed(4)} sub="txns/day" />
                    <StatCard label="Locations" value={data.profile.location_profile?.join(", ")} />
                  </div>
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <p className={labelCls}>Known Devices</p>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {data.profile.device_list?.map((d) => (
                          <span key={d} className="text-xs px-2.5 py-1 rounded-full border font-mono" style={{ borderColor: C.border, color: C.text }}>{d}</span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className={labelCls}>Active Hours</p>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {data.profile.active_hours?.map((h) => (
                          <span key={h} className="text-xs px-2.5 py-1 rounded-full border font-mono" style={{ borderColor: C.gold, color: C.gold }}>{String(h).padStart(2,"0")}:00</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {!data && !loading && !error && (
            <div className="rounded-xl border p-12 text-center text-sm border-dashed" style={{ borderColor: C.border, color: C.muted }}>
              Enter an Account ID above and click Load Metrics to view analytics.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
