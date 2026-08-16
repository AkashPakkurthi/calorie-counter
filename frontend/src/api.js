const BASE = import.meta.env.VITE_API_URL || "";

export class AuthError extends Error {}

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    // the session lives in an httpOnly cookie, so it must be sent along
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (res.status === 401) {
    throw new AuthError(data?.detail || "Not signed in");
  }
  if (!res.ok) {
    throw new Error(data?.detail || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  health: () => request("/api/health"),

  authConfig: () => request("/api/auth/config"),
  me: () => request("/api/auth/me"),
  register: (payload) => request("/api/auth/register", { method: "POST", body: payload }),
  login: (email, password) =>
    request("/api/auth/login", { method: "POST", body: { email, password } }),
  logout: () => request("/api/auth/logout", { method: "POST" }),

  day: (date = "today") => request(`/api/days/${date}`),
  days: (days = 30) => request(`/api/days?days=${days}`),

  analyze: (text, meal_type) =>
    request("/api/meals/analyze", { method: "POST", body: { text, meal_type } }),
  saveMeal: (payload) => request("/api/meals", { method: "POST", body: payload }),
  pickMeal: (payload) => request("/api/meals/pick", { method: "POST", body: payload }),
  deleteMeal: (id) => request(`/api/meals/${id}`, { method: "DELETE" }),

  settings: () => request("/api/settings"),
  saveSettings: (payload) => request("/api/settings", { method: "PUT", body: payload }),

  plan: () => request("/api/settings/plan"),
  saveGoal: (payload) => request("/api/settings/goal", { method: "PUT", body: payload }),
  clearGoal: () => request("/api/settings/goal", { method: "DELETE" }),

  foodOptions: (q = "") =>
    request(`/api/foods/options${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  foods: () => request("/api/foods"),
  updateFood: (id, payload) => request(`/api/foods/${id}`, { method: "PATCH", body: payload }),
  deleteFood: (id) => request(`/api/foods/${id}`, { method: "DELETE" }),

  activity: (date = "today") => request(`/api/activity/${date}`),
  saveActivity: (date, payload) =>
    request(`/api/activity/${date}`, { method: "PUT", body: payload }),
  activityRates: () => request("/api/activity/rates"),

  water: (date = "today") => request(`/api/water/${date}`),
  saveWater: (date, ml) => request(`/api/water/${date}`, { method: "PUT", body: { ml } }),

  weights: () => request("/api/weight"),
  logWeight: (weight_kg, date) =>
    request("/api/weight", { method: "POST", body: { weight_kg, date } }),

  favourites: () => request("/api/favourites"),
  createFavourite: (payload) =>
    request("/api/favourites", { method: "POST", body: payload }),
  logFavourite: (id, payload) =>
    request(`/api/favourites/${id}/log`, { method: "POST", body: payload || {} }),
  deleteFavourite: (id) => request(`/api/favourites/${id}`, { method: "DELETE" }),
};

export const MEALS = [
  { key: "breakfast", label: "Breakfast", emoji: "☀️" },
  { key: "lunch", label: "Lunch", emoji: "🍛" },
  { key: "dinner", label: "Dinner", emoji: "🌙" },
  { key: "snacks", label: "Snacks", emoji: "🥜" },
];

export const UNITS = ["piece", "g", "ml", "bowl", "cup", "tbsp", "slice", "serving"];
