/*
 * Funnel event tracking for GA4 (gtag), shared by App/ExportBar/CtaBand.
 * outbound-analytics.js already covers link clicks (outbound_click,
 * contact_click) via a delegated listener; the scan funnel's own steps
 * (submit, result, export, lead) aren't link clicks, so they need explicit
 * calls at the point each thing actually happens. Same "drop silently if
 * gtag hasn't loaded" contract as that file, so this is safe to call
 * unconditionally from anywhere in the app.
 */
export function trackEvent(name, params) {
  if (typeof window !== "undefined" && typeof window.gtag === "function") {
    window.gtag("event", name, params);
  }
}
