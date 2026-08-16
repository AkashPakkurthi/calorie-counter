import { useQuery } from "@tanstack/react-query";
import { useOutletContext } from "react-router-dom";

import { api, MEALS } from "../api.js";
import { CalorieRing, MacroBar, MicroStat } from "../components/Rings.jsx";
import MealCard from "../components/MealCard.jsx";
import {
  ActivityCard,
  FavouritesStrip,
  WaterCard,
  WeightCard,
} from "../components/SideCards.jsx";
import { Card, ErrorNote, Spinner } from "../components/ui.jsx";

const MACROS = [
  ["Protein", "protein_g", "var(--color-series-3)"],
  ["Carbs", "carbs_g", "var(--color-series-2)"],
  ["Fat", "fat_g", "var(--color-series-4)"],
  ["Fiber", "fiber_g", "var(--color-series-5)"],
];

export default function Dashboard() {
  const { user } = useOutletContext();

  const { data: day, isLoading, error } = useQuery({
    queryKey: ["day", "today"],
    queryFn: () => api.day("today"),
  });

  const { data: health } = useQuery({ queryKey: ["health"], queryFn: api.health });

  if (isLoading) return <Spinner label="Loading today" />;
  if (error) return <ErrorNote>{error.message}</ErrorNote>;

  const { totals, targets, meals, activity, water } = day;
  const prettyDate = new Date(`${day.date}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <div className="space-y-4">
      {health && !health.openai_configured && (
        <ErrorNote>
          No API key configured, so “Type it” won’t work — picking known foods
          still does. Set <code>OPENAI_API_KEY</code> (plus{" "}
          <code>OPENAI_BASE_URL</code> and <code>OPENAI_MODEL</code> if you use
          Groq or another provider) in your hosting platform’s variables, or in{" "}
          <code>.env</code> when running locally, then restart.
        </ErrorNote>
      )}

      <div className="flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">
          {user?.name ? `${user.name} — ${prettyDate}` : prettyDate}
        </h1>
        <span className="text-sm text-ink-500">{day.date}</span>
      </div>

      <Card>
        <CalorieRing
          consumed={totals.calories}
          target={targets.daily_calories}
          burned={activity.calories_burned}
          net={day.net_calories}
        />
      </Card>

      <Card title="Macros">
        <div className="grid gap-3 sm:grid-cols-2">
          {MACROS.map(([label, key, color]) => (
            <MacroBar
              key={key}
              label={label}
              value={totals[key]}
              target={targets[key]}
              color={color}
            />
          ))}
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          <MicroStat label="Sugar" value={totals.sugar_g} unit="g" />
          <MicroStat label="Sodium" value={totals.sodium_mg} unit="mg" />
          <MicroStat label="Net kcal" value={day.net_calories} unit="" />
        </div>
      </Card>

      <FavouritesStrip date={day.date} />

      <div className="grid gap-4 sm:grid-cols-2">
        {MEALS.map((meal) => (
          <MealCard key={meal.key} meal={meal} date={day.date} meals={meals[meal.key]} />
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <ActivityCard date={day.date} activity={activity} />
        <WaterCard date={day.date} water={water} target={targets.water_target_ml} />
        <WeightCard currentWeight={day.weight_kg} staleDays={day.weight_stale_days} />
      </div>
    </div>
  );
}
