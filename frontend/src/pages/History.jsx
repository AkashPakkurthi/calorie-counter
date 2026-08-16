import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, MEALS } from "../api.js";
import { Button, Card, Input, Spinner, fmt } from "../components/ui.jsx";

const AXIS = { stroke: "var(--color-ink-500)", fontSize: 11 };
const GRID = "var(--color-ink-800)";

const shortDate = (d) =>
  new Date(`${d}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });

function ChartTooltip({ active, payload, label, unit = "" }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 text-ink-300">{shortDate(label)}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="tnum flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-sm"
            style={{ background: p.color }}
            aria-hidden
          />
          <span className="text-ink-300">{p.name}</span>
          <span className="ml-auto font-medium">
            {fmt(p.value)}
            {unit}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function History() {
  const [range, setRange] = useState(30);
  const [openDate, setOpenDate] = useState("");

  const { data: days = [], isLoading } = useQuery({
    queryKey: ["days", range],
    queryFn: () => api.days(range),
  });
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  if (isLoading) return <Spinner label="Loading history" />;

  const weightSeries = days.filter((d) => d.weight_kg !== null);

  const byWeekday = Array.from({ length: 7 }, (_, i) => ({ day: i, total: 0, n: 0 }));
  days.forEach((d) => {
    const idx = new Date(`${d.date}T00:00:00`).getDay();
    if (d.calories > 0) {
      byWeekday[idx].total += d.calories;
      byWeekday[idx].n += 1;
    }
  });
  const weekdayData = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((name, i) => ({
    name,
    avg: byWeekday[i].n ? Math.round(byWeekday[i].total / byWeekday[i].n) : 0,
  }));

  const logged = days.filter((d) => d.calories > 0);
  const avgCalories = logged.length
    ? Math.round(logged.reduce((s, d) => s + d.calories, 0) / logged.length)
    : 0;
  const avgProtein = logged.length
    ? Math.round(logged.reduce((s, d) => s + d.protein_g, 0) / logged.length)
    : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">History</h1>
        <div className="flex gap-1 rounded-lg bg-ink-850 p-1 text-sm">
          {[7, 30, 90].map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`rounded-md px-3 py-1 transition ${
                range === r ? "bg-ink-700 text-ink-100" : "text-ink-300 hover:text-ink-100"
              }`}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card title="Days logged">
          <p className="tnum text-3xl font-semibold">{logged.length}</p>
        </Card>
        <Card title="Avg calories">
          <p className="tnum text-3xl font-semibold">{fmt(avgCalories)}</p>
          <p className="text-xs text-ink-500">
            target {fmt(settings?.daily_calories)}
          </p>
        </Card>
        <Card title="Avg protein">
          <p className="tnum text-3xl font-semibold">
            {avgProtein}
            <span className="ml-1 text-base font-normal text-ink-500">g</span>
          </p>
          <p className="text-xs text-ink-500">target {settings?.protein_g}g</p>
        </Card>
      </div>

      <Card title="Calories per day">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={days} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} {...AXIS} />
            <YAxis
              // keep the target line inside the plot even on light-eating days
              domain={[0, (max) => Math.max(max * 1.1, (settings?.daily_calories || 0) * 1.05)]}
              tickLine={false}
              axisLine={false}
              {...AXIS}
            />
            {settings && (
              <ReferenceLine
                y={settings.daily_calories}
                stroke="var(--color-ink-500)"
                strokeDasharray="4 4"
                label={{ value: "target", fill: "var(--color-ink-500)", fontSize: 11 }}
              />
            )}
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: GRID }} />
            <Line
              type="monotone"
              dataKey="calories"
              name="Calories"
              stroke="var(--color-series-1)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card title="Protein per day">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={days} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} {...AXIS} />
              <YAxis
                domain={[0, (max) => Math.max(max * 1.1, (settings?.protein_g || 0) * 1.05)]}
                tickLine={false}
                axisLine={false}
                {...AXIS}
              />
              {settings && (
                <ReferenceLine
                  y={settings.protein_g}
                  stroke="var(--color-ink-500)"
                  strokeDasharray="4 4"
                />
              )}
              <Tooltip content={<ChartTooltip unit="g" />} cursor={{ stroke: GRID }} />
              <Line
                type="monotone"
                dataKey="protein_g"
                name="Protein"
                stroke="var(--color-series-3)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Weight">
          {weightSeries.length > 1 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart
                data={weightSeries}
                margin={{ top: 8, right: 12, bottom: 0, left: -18 }}
              >
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="date" tickFormatter={shortDate} tickLine={false} {...AXIS} />
                <YAxis
                  domain={["dataMin - 1", "dataMax + 1"]}
                  tickLine={false}
                  axisLine={false}
                  {...AXIS}
                />
                <Tooltip content={<ChartTooltip unit=" kg" />} cursor={{ stroke: GRID }} />
                <Line
                  type="monotone"
                  dataKey="weight_kg"
                  name="Weight"
                  stroke="var(--color-series-2)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-12 text-center text-sm text-ink-500">
              Log a weigh-in for two weeks and the trend shows up here.
            </p>
          )}
        </Card>
      </div>

      <Card title="Average by weekday">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={weekdayData} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="name" tickLine={false} {...AXIS} />
            <YAxis tickLine={false} axisLine={false} {...AXIS} />
            <Tooltip
              cursor={{ fill: "var(--color-ink-850)" }}
              contentStyle={{
                background: "var(--color-ink-850)",
                border: "1px solid var(--color-ink-700)",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Bar dataKey="avg" name="Avg kcal" fill="var(--color-series-1)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Open a day">
        <div className="flex gap-2">
          <Input
            type="date"
            value={openDate}
            onChange={(e) => setOpenDate(e.target.value)}
          />
        </div>
        {openDate && <DayDetail date={openDate} />}
      </Card>
    </div>
  );
}

function DayDetail({ date }) {
  const { data: day, isLoading } = useQuery({
    queryKey: ["day", date],
    queryFn: () => api.day(date),
  });
  if (isLoading) return <Spinner label="Loading day" />;
  if (!day) return null;

  return (
    <div className="mt-4 space-y-3">
      <div className="tnum grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          ["Calories", day.totals.calories],
          ["Protein", day.totals.protein_g],
          ["Carbs", day.totals.carbs_g],
          ["Fat", day.totals.fat_g],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl bg-ink-850 px-3 py-2">
            <div className="text-[11px] text-ink-500 uppercase">{label}</div>
            <div className="text-lg font-semibold">{fmt(value)}</div>
          </div>
        ))}
      </div>
      {MEALS.map((meal) => {
        const items = day.meals[meal.key].flatMap((m) => m.items);
        if (!items.length) return null;
        return (
          <div key={meal.key}>
            <h3 className="text-sm font-medium text-ink-300">
              {meal.emoji} {meal.label}
            </h3>
            <ul className="mt-1 text-sm text-ink-100">
              {items.map((i) => (
                <li key={i.id} className="tnum flex justify-between py-0.5">
                  <span>
                    {i.name}{" "}
                    <span className="text-ink-500">
                      {i.quantity} {i.unit}
                    </span>
                  </span>
                  <span>{fmt(i.calories)}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <p className="text-xs text-ink-500">
        Burned {fmt(day.activity.calories_burned)} kcal at {day.activity.weight_used_kg} kg ·
        Net {fmt(day.net_calories)} kcal
      </p>
    </div>
  );
}
