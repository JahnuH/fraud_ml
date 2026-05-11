import { useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  useMapEvents,
} from "react-leaflet";
import API, { getHealth, postScoreBehaviour } from "../services/api";

import { C, cls } from "../styles";

import "leaflet/dist/leaflet.css";

export default function TestPage() {
  const [position, setPosition] = useState([12.9716, 77.5946]);

  const [formData, setFormData] = useState({
    latitude: "12.9716",
    longitude: "77.5946",
    eventId: "",
    accountId: "",
    instrumentId: "",
    eventDate: "",
    eventTime: "",
    amount: "",
    currency: "",
    mcc: "",
    country: "",
    ip: "",
    deviceFingerprint: "",
    merchantId: "",
    entryMode: "",
    terminalId: "",
    transactionType: "",
  });

  const [response, setResponse] = useState(null);
  const [apiHealth, setApiHealth] = useState(null);
  const [now, setNow] = useState(new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const checkHealth = async () => {
    console.log("[FRMS] Checking API health...");
    try {
      const { data } = await getHealth();
      console.log("[FRMS] Health OK:", data);
      setApiHealth({ ok: true, data });
    } catch (err) {
      console.error("[FRMS] Health FAILED:", err.message);
      setApiHealth({ ok: false });
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setNow(new Date());
    setResponse(null);
    await checkHealth();
    setRefreshing(false);
  };

  const handleChange = (e) =>
    setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleCoordBlur = (e) => {
    const { name, value } = e.target;
    const parsed = parseFloat(value);
    if (!isNaN(parsed)) {
      const clamped = parseFloat(parsed.toFixed(4));
      setFormData((p) => ({ ...p, [name]: String(clamped) }));
      if (name === "latitude" || name === "longitude") {
        setPosition((prev) =>
          name === "latitude" ? [clamped, parseFloat(prev[1])] : [parseFloat(prev[0]), clamped]
        );
      }
    }
  };

  function MapClickHandler() {
    useMapEvents({
      click(e) {
        const lat = e.latlng.lat.toFixed(4);
        const lng = e.latlng.lng.toFixed(4);
        setPosition([lat, lng]);
        setFormData((prev) => ({ ...prev, latitude: lat, longitude: lng }));
      },
    });
    return null;
  }

  const handleSubmit = async () => {
    // Validate mandatory fields
    if (!formData.accountId || !formData.eventDate || !formData.eventTime || !formData.amount) {
      setResponse({ error: "Missing required fields: Account ID, Event Date, Event Time, and Amount are mandatory." });
      return;
    }

    setSubmitting(true);
    setResponse(null);
    const payload = {
      account_id: formData.accountId,
      event_id: formData.eventId,
      instrument_id: formData.instrumentId,
      event_ts: formData.eventDate && formData.eventTime
        ? `${formData.eventDate}T${formData.eventTime}`
        : undefined,
      amount: parseFloat(formData.amount) || undefined,
      currency: formData.currency,
      country: formData.country,
      mcc: formData.mcc,
      merchant_id: formData.merchantId,
      entry_mode: formData.entryMode,
      ip: formData.ip,
      device_fingerprint: formData.deviceFingerprint,
      terminal_id: formData.terminalId,
      txn_type: formData.transactionType,
      geo_coordinates: [
        parseFloat(parseFloat(formData.latitude).toFixed(4)),
        parseFloat(parseFloat(formData.longitude).toFixed(4)),
      ],
    };
    console.log("[FRMS] POST /score-behaviour → payload:", payload);
    try {
      const { data } = await postScoreBehaviour(payload);
      console.log("[FRMS] POST /score-behaviour ← response:", data);
      setResponse(data);
    } catch (error) {
      const err = error?.response?.data || error.message;
      console.error("[FRMS] POST /score-behaviour ← error:", err);
      setResponse({ error: err });
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls = cls.input;
  const labelCls = cls.label;

  return (
    <div className="min-h-screen flex font-sans" style={{ background: C.sand }}>

      {/* SIDEBAR */}
      <aside
        className="w-56 hidden lg:flex flex-col py-8 px-5 border-r shrink-0 sticky top-0 h-screen"
        style={{ background: C.navy, borderColor: "#243447" }}
      >
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

        <p className="text-[10px] font-bold uppercase tracking-widest mb-3 px-1" style={{ color: "#4A6080" }}>
          Navigation
        </p>

        <nav className="space-y-0.5">
          {[
            ["Single Transaction", "/test"],
            ["Bulk Simulator", "/bulk"],
            ["Metrics", "/metrics"],
          ].map(([label, href]) => {
            const active = window.location.pathname === href;
            return (
              <a
                key={label}
                href={href}
                className="w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2.5"
                style={
                  active
                    ? { background: "#243447", color: C.gold, borderLeft: `2px solid ${C.gold}` }
                    : { color: C.muted, borderLeft: "2px solid transparent" }
                }
              >
                {label}
              </a>
            );
          })}
        </nav>

        <div className="mt-auto pt-5 border-t px-1" style={{ borderColor: "#243447" }}>
          <p className="text-[10px]" style={{ color: "#4A6080" }}>v1.0.0 · FRMS</p>
        </div>
      </aside>

      {/* MAIN */}
      <main className="flex-1 overflow-y-auto">

        {/* TOP BAR */}
        <div
          className="sticky top-0 z-10 px-8 py-4 flex items-center justify-between border-b"
          style={{ background: C.sand, borderColor: C.border }}
        >
          <div>
            <h1 className="text-lg font-bold tracking-tight" style={{ color: C.text }}>
              Behavioral Anomaly Detection
            </h1>
            <p className="text-xs mt-0.5" style={{ color: C.muted }}>
              Fraud Risk Monitoring · Single Transaction
            </p>
          </div>

          {/* REFRESH BUTTON — standalone, refreshes entire page state */}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh page state"
            className="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-semibold transition-all"
            style={{ borderColor: refreshing ? C.gold : C.border, color: refreshing ? C.gold : C.text, background: C.white, opacity: refreshing ? 0.8 : 1 }}
            onMouseEnter={(e) => { if (!refreshing) { e.currentTarget.style.borderColor = C.gold; e.currentTarget.style.color = C.gold; } }}
            onMouseLeave={(e) => { if (!refreshing) { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.color = C.text; } }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              style={{ animation: refreshing ? "spin 0.8s linear infinite" : "none" }}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <div className="p-8 space-y-6">

          {/* STAT CARDS */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

            <div className="rounded-xl p-5 border" style={{ background: C.white, borderColor: C.border }}>
              <p className={labelCls}>Date</p>
              <h2 className="text-base font-semibold mt-1" style={{ color: C.text }}>
                {now.toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" })}
              </h2>
            </div>

            <div className="rounded-xl p-5 border" style={{ background: C.white, borderColor: C.border }}>
              <p className={labelCls}>Time</p>
              <h2 className="text-base font-semibold mt-1 font-mono" style={{ color: C.text }}>
                {now.toLocaleTimeString()}
              </h2>
            </div>

            <div className="rounded-xl p-5 border" style={{ background: C.white, borderColor: C.border }}>
              <p className={labelCls}>API Health</p>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{
                    background:
                      apiHealth === null ? C.border :
                      apiHealth.ok ? C.green : C.red,
                  }}
                />
                <h2
                  className="text-base font-semibold"
                  style={{
                    color:
                      apiHealth === null ? C.muted :
                      apiHealth.ok ? C.green : C.red,
                  }}
                >
                  {apiHealth === null ? "Not checked" : apiHealth.ok ? "Healthy" : "Unreachable"}
                </h2>
              </div>
              {apiHealth?.ok && apiHealth.data && (
                <div className="mt-1.5 space-y-0.5">
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                    {["status", "service"].map((k) => apiHealth.data[k] && (
                      <span key={k} className="text-[10px] font-mono" style={{ color: C.muted }}>
                        <span style={{ color: C.text }}>{k}</span>: {String(apiHealth.data[k])}
                      </span>
                    ))}
                  </div>
                  {apiHealth.data.database && (
                    <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                      <span className="text-[10px] font-mono" style={{ color: C.muted }}>
                        <span style={{ color: C.text }}>db</span>: {apiHealth.data.database.status}
                      </span>
                      {Object.entries(apiHealth.data.database.table_counts ?? {}).map(([k, v]) => (
                        <span key={k} className="text-[10px] font-mono" style={{ color: C.muted }}>
                          <span style={{ color: C.text }}>{k.replace(/_/g, " ")}</span>: {v}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

          </div>

          {/* FORM PANEL */}
          <div className="rounded-xl border overflow-hidden" style={{ background: C.white, borderColor: C.border }}>

            {/* Panel header */}
            <div className="px-7 py-5 border-b flex items-center justify-between" style={{ borderColor: C.border }}>
              <div>
                <h2 className="text-sm font-bold uppercase tracking-widest" style={{ color: C.text }}>
                  Single Transaction Tester
                </h2>
                <p className="text-xs mt-0.5" style={{ color: C.muted }}>
                  Configure and evaluate a transaction payload
                </p>
              </div>
              <span
                className="text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full border"
                style={{ borderColor: C.border, color: C.muted }}
              >
                Manual
              </span>
            </div>

            <div className="p-7 space-y-7">

              {/* MAP */}
              <div>
                <div className="flex flex-col sm:flex-row gap-4 mb-4">
                  <div className="flex-1">
                    <label className={labelCls}>Latitude</label>
                    <input type="text" name="latitude" value={formData.latitude} onChange={handleChange} onBlur={handleCoordBlur} className={inputCls} />
                  </div>
                  <div className="flex-1">
                    <label className={labelCls}>Longitude</label>
                    <input type="text" name="longitude" value={formData.longitude} onChange={handleChange} onBlur={handleCoordBlur} className={inputCls} />
                  </div>
                </div>
                <div className="overflow-hidden rounded-lg border relative z-0" style={{ borderColor: C.border }}>
                  <MapContainer
                    center={position}
                    zoom={4}
                    style={{ height: "280px", width: "100%" }}
                    maxBounds={[[-90, -180], [90, 180]]}
                    maxBoundsViscosity={1.0}
                    worldCopyJump={false}
                  >
                    <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <Marker position={position} />
                    <MapClickHandler />
                  </MapContainer>
                </div>
              </div>

              {/* FORM FIELDS */}
              <div>
                <p className={labelCls + " mb-4"}>Transaction Fields</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-5 gap-y-5">
                  {[
                    ["eventId", "Event ID"],
                    ["accountId", "Account ID"],
                    ["instrumentId", "Instrument ID"],
                    ["eventDate", "Event Date", "date"],
                    ["eventTime", "Event Time", "time"],
                    ["amount", "Amount"],
                    ["currency", "Currency"],
                    ["mcc", "MCC"],
                    ["country", "Country"],
                    ["ip", "IP Address"],
                    ["deviceFingerprint", "Device Fingerprint"],
                    ["merchantId", "Merchant ID"],
                    ["entryMode", "Entry Mode"],
                    ["terminalId", "Terminal ID"],
                    ["transactionType", "Transaction Type"],
                  ].map(([key, label, type = "text"]) => {
                    const required = ["accountId", "eventDate", "eventTime", "amount"].includes(key);
                    const missing = required && !formData[key];
                    return (
                      <div key={key}>
                        <label className={labelCls}>
                          {label}
                          {required && <span className="ml-1 font-bold" style={{ color: C.red }}>*</span>}
                        </label>
                        <input
                          type={type}
                          name={key}
                          value={formData[key]}
                          onChange={handleChange}
                          placeholder={label}
                          className={inputCls}
                          style={missing ? { borderColor: C.red } : {}}
                        />
                        {missing && (
                          <p className="text-[10px] mt-1" style={{ color: C.red }}>Required</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* ACTIONS */}
              <div className="pt-4 border-t space-y-3" style={{ borderColor: C.border }}>
                {(!formData.accountId || !formData.eventDate || !formData.eventTime || !formData.amount) && (
                  <p className="text-xs" style={{ color: C.red }}>
                    * Account ID, Event Date, Event Time, and Amount are required to run detection.
                  </p>
                )}
                <div className="flex justify-end">
                  <button
                    onClick={handleSubmit}
                    disabled={submitting || !formData.accountId || !formData.eventDate || !formData.eventTime || !formData.amount}
                    className="px-8 py-2.5 rounded-lg text-sm font-bold tracking-wide uppercase transition-all"
                    style={{
                      background: C.gold,
                      color: C.white,
                      opacity: (submitting || !formData.accountId || !formData.eventDate || !formData.eventTime || !formData.amount) ? 0.5 : 1
                    }}
                    onMouseEnter={(e) => { if (!submitting) e.currentTarget.style.opacity = "0.88"; }}
                    onMouseLeave={(e) => { if (!submitting) e.currentTarget.style.opacity = "1"; }}
                  >
                    {submitting ? "Running..." : "Run Detection"}
                  </button>
                </div>
              </div>

            </div>
          </div>

          {/* RESPONSE PANEL */}
          <div className="rounded-xl border overflow-hidden" style={{ background: C.navy, borderColor: "#243447" }}>
            <div className="px-6 py-4 border-b flex items-center gap-2" style={{ borderColor: "#243447" }}>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke={C.gold} strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <h2 className="text-xs font-bold uppercase tracking-widest" style={{ color: C.muted }}>Detection Result</h2>
            </div>

            <div className="p-6">
              {!response ? (
                <div className="rounded-lg p-8 text-center text-sm border border-dashed" style={{ borderColor: "#2D4A5E", color: "#4A6080" }}>
                  Run detection to view the response payload here.
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
                  {/* Score + Change banner */}
                  <div className={`rounded-lg p-5 border flex items-center justify-between`}
                    style={{
                      background: response.behaviour_change ? "#2A1A1E" : "#162A1E",
                      borderColor: response.behaviour_change ? C.red : C.green,
                    }}
                  >
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-widest mb-1" style={{ color: response.behaviour_change ? C.red : C.green }}>
                        {response.behaviour_change ? "⚠ Behaviour Change Detected" : "✓ No Behaviour Change"}
                      </p>
                      <p className="text-3xl font-bold font-mono" style={{ color: response.behaviour_change ? "#F4A0A0" : "#86EFAC" }}>
                        {(response.behaviour_score * 100).toFixed(2)}%
                      </p>
                      <p className="text-xs mt-1" style={{ color: C.muted }}>Behaviour Score</p>
                    </div>
                    {/* Score gauge bar */}
                    <div className="w-32">
                      <div className="h-2 rounded-full overflow-hidden" style={{ background: "#243447" }}>
                        <div
                          className="h-2 rounded-full transition-all"
                          style={{
                            width: `${Math.min(response.behaviour_score * 100, 100)}%`,
                            background: response.behaviour_change ? C.red : C.green,
                          }}
                        />
                      </div>
                      <p className="text-[10px] mt-1 text-right font-mono" style={{ color: C.muted }}>
                        {(response.behaviour_score * 100).toFixed(2)} / 100
                      </p>
                    </div>
                  </div>

                  {/* Reasons */}
                  <div className="rounded-lg p-5 border" style={{ background: "#131F2B", borderColor: "#243447" }}>
                    <p className="text-[11px] font-bold uppercase tracking-widest mb-3" style={{ color: C.muted }}>Anomaly Reasons</p>
                    {response.reasons?.length === 0 ? (
                      <p className="text-sm" style={{ color: "#86EFAC" }}>No anomaly reasons — transaction appears normal.</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {response.reasons.map((r) => (
                          <span key={r} className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide border"
                            style={{ background: "#2A1A1E", borderColor: C.red, color: "#F4A0A0" }}
                          >
                            {r.replace(/_/g, " ")}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Raw JSON toggle */}
                  <details className="rounded-lg border overflow-hidden" style={{ borderColor: "#243447" }}>
                    <summary className="px-4 py-2.5 text-xs font-bold uppercase tracking-widest cursor-pointer" style={{ background: "#1A2A38", color: C.muted }}>Raw JSON</summary>
                    <pre className="p-4 overflow-auto text-xs font-mono max-h-[300px]" style={{ background: "#131F2B", color: "#E2C98A" }}>
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
