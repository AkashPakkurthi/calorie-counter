import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Today" },
  { to: "/history", label: "History" },
  { to: "/foods", label: "Foods" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="min-h-screen bg-ink-950">
      <header className="sticky top-0 z-20 border-b border-ink-800 bg-ink-950/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">🔥</span>
            <span className="font-semibold tracking-tight">Calorie Tracker</span>
          </div>
          <nav className="flex gap-1 text-sm">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 transition ${
                    isActive
                      ? "bg-ink-800 text-ink-100"
                      : "text-ink-300 hover:bg-ink-900 hover:text-ink-100"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 pb-24">
        <Outlet />
      </main>
    </div>
  );
}
