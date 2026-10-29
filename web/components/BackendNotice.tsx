import { apiBaseUrl } from "@/lib/api";

export function BackendNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  const base = apiBaseUrl();
  const showLocalCommand = process.env.NODE_ENV !== "production";
  return (
    <div className="rounded-xl border border-line bg-raised px-5 py-6" role="alert">
      <h2 className="font-serif text-2xl tracking-tight">The investigation API is not available</h2>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">{message}</p>
      {showLocalCommand ? (
        <pre className="mt-4 overflow-x-auto rounded-lg border border-line bg-paper px-4 py-3 font-mono text-xs leading-relaxed text-ink">
          uvicorn campaign_doctor.api.app:app --reload --port 8000
        </pre>
      ) : null}
      {base ? <p className="mt-3 font-mono text-xs text-muted">Trying {base}</p> : null}
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 rounded-full border border-pine bg-pine px-4 py-2 text-sm text-raised"
      >
        Try again
      </button>
    </div>
  );
}
