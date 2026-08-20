import { NavLink, Outlet } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api.js";
import Login from "./pages/Login.jsx";
import { Spinner } from "./components/ui.jsx";

const links = [
  { to: "/", label: "Today" },
  { to: "/history", label: "History" },
  { to: "/foods", label: "Foods" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  const qc = useQueryClient();

  // The session is an httpOnly cookie, so the only way to know whether we are
  // signed in is to ask the server.
  const { data: user, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: false,
  });

  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.clear(); // drop every cached page of the old account
      window.location.assign("/");
    },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Signing you in" />
      </div>
    );
  }

  // Presence of user data is the single source of truth. Checking the query's
  // error state as well would keep us on the login screen after a successful
  // sign-in, because that first 401 stays recorded on the query.
  if (!user) {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-ink-950">
      <header className="sticky top-0 z-20 border-b border-ink-800 bg-ink-950/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">🔥</span>
            <span className="font-semibold tracking-tight">Akash Calorie Tracker</span>
          </div>
          <nav className="flex items-center gap-1 text-sm">
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
            <button
              onClick={() => logout.mutate()}
              title={`Signed in as ${user.email}`}
              className="ml-1 rounded-lg px-3 py-1.5 text-ink-500 transition hover:bg-ink-900 hover:text-ink-100"
            >
              {logout.isPending ? "…" : "Sign out"}
            </button>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 pb-24">
        <Outlet context={{ user }} />
      </main>
    </div>
  );
}
