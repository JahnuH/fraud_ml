// ─── APP CONFIG ──────────────────────────────────────────────────────────────
// Single place to update branding, navigation, and app metadata.

const appConfig = {
  // Branding
  appName:    "FRMS",
  appTagline: "Fraud Risk Monitoring",
  version:    "1.0.0",

  // Navigation links
  // active: true marks the currently selected item (update when routing is added)
  navLinks: [
    { label: "Single Transaction", active: true },
    { label: "Bulk Simulator",     active: false },
    { label: "Metrics",            active: false },
  ],

  // Page header
  pageTitle:    "Behavioral Anomaly Detection",
  pageSubtitle: "Fraud Risk Monitoring · Single Transaction",
};

export default appConfig;
