export default function LoadingState() {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p>Scanning your page&hellip; this can take up to 30 seconds.</p>
    </div>
  );
}
