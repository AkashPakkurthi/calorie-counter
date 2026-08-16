export function Card({ title, action, className = "", children }) {
  return (
    <section
      className={`rounded-2xl border border-ink-800 bg-ink-900 p-4 shadow-sm ${className}`}
    >
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium tracking-wide text-ink-300 uppercase">
            {title}
          </h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}) {
  const styles = {
    // dark ink on the blue fill: white would only reach 3.6:1
    primary: "bg-series-1 text-ink-950 hover:brightness-110",
    ghost: "bg-ink-800 text-ink-100 hover:bg-ink-700",
    quiet: "text-ink-300 hover:text-ink-100 hover:bg-ink-800",
    danger: "text-over hover:bg-ink-800",
  }[variant];
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  );
}

export function Input({ className = "", ...props }) {
  return (
    <input
      className={`w-full rounded-lg border border-field bg-ink-850 px-3 py-2 text-sm text-ink-100 outline-none placeholder:text-ink-500 focus:border-series-1 focus:ring-1 focus:ring-series-1 ${className}`}
      {...props}
    />
  );
}

export function Select({ className = "", ...props }) {
  return (
    <select
      className={`rounded-lg border border-field bg-ink-850 px-2 py-2 text-sm text-ink-100 outline-none focus:border-series-1 focus:ring-1 focus:ring-series-1 ${className}`}
      {...props}
    />
  );
}

export function Spinner({ label = "Loading" }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-ink-500">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-ink-700 border-t-series-1" />
      {label}…
    </div>
  );
}

export function ErrorNote({ children }) {
  if (!children) return null;
  return (
    <p className="mt-2 rounded-lg border border-over/40 bg-over/10 px-3 py-2 text-sm text-over">
      {children}
    </p>
  );
}

export function Modal({ open, onClose, title, children, wide = false }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`max-h-[90vh] w-full overflow-y-auto rounded-t-2xl border border-ink-800 bg-ink-900 p-4 sm:rounded-2xl ${
          wide ? "sm:max-w-3xl" : "sm:max-w-lg"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-semibold">{title}</h3>
          <Button variant="quiet" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}

export const round = (n) => Math.round((n || 0) * 10) / 10;
export const fmt = (n) => Math.round(n || 0).toLocaleString();
