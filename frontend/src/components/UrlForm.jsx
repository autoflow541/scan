import { useState } from "react";

// Client-side sanity check only -- real validation (SSRF, DNS, scheme) happens
// server-side. This just catches obviously-empty or non-url-ish input before
// we bother the backend.
function looksLikeUrl(value) {
  const trimmed = value.trim();
  if (!trimmed) return false;
  try {
    const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    const parsed = new URL(withScheme);
    return parsed.hostname.includes(".");
  } catch {
    return false;
  }
}

export default function UrlForm({ onSubmit, disabled }) {
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);

  const valid = looksLikeUrl(value);

  function handleSubmit(e) {
    e.preventDefault();
    setTouched(true);
    if (!valid || disabled) return;
    const trimmed = value.trim();
    const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    onSubmit(withScheme);
  }

  return (
    <form className="url-form" onSubmit={handleSubmit}>
      <label htmlFor="scan-url" className="sr-only" style={{ position: "absolute", left: "-9999px" }}>
        URL to scan
      </label>
      <input
        id="scan-url"
        className="url-input"
        type="text"
        inputMode="url"
        placeholder="https://example.com"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={disabled}
        aria-invalid={touched && !valid}
      />
      <button type="submit" className="scan-button" disabled={disabled}>
        {disabled ? "Scanning..." : "Scan this page"}
      </button>
      {touched && !valid && (
        <p className="url-hint" role="alert">Enter a full URL, e.g. https://example.com</p>
      )}
    </form>
  );
}
