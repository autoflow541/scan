const MESSAGES = {
  400: "That URL isn't one we can scan (it may point at a private or internal address, or use an unsupported scheme).",
  422: "We couldn't load that page. Double-check the URL is correct and publicly reachable.",
  429: "You've hit the scan limit for now. Wait a bit and try again.",
  504: "The scan timed out. The page may be slow to load or temporarily unreachable.",
};

export default function ErrorState({ error }) {
  const message = (error && MESSAGES[error.status]) || (error && error.message) || "Something went wrong. Please try again.";
  return (
    <div className="error-state" role="alert">
      <h2>Couldn't complete that scan</h2>
      <p>{message}</p>
    </div>
  );
}
