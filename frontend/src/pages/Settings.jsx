import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api.js";
import { Button, Card, ErrorNote, Input, Spinner } from "../components/ui.jsx";

const TARGETS = [
  ["daily_calories", "Daily calories", "kcal"],
  ["protein_g", "Protein", "g"],
  ["carbs_g", "Carbs", "g"],
  ["fat_g", "Fat", "g"],
  ["fiber_g", "Fiber", "g"],
  ["water_target_ml", "Water", "ml"],
];

const PROFILE = [
  ["weight_kg", "Weight", "kg"],
  ["height_cm", "Height", "cm"],
  ["age", "Age", "yrs"],
];

const PRESETS = [
  { label: "Cut", daily_calories: 2000, protein_g: 170, carbs_g: 180, fat_g: 60, fiber_g: 30 },
  { label: "Maintain", daily_calories: 2500, protein_g: 150, carbs_g: 280, fat_g: 80, fiber_g: 30 },
  { label: "Lean bulk", daily_calories: 2800, protein_g: 170, carbs_g: 330, fat_g: 85, fiber_g: 35 },
];

/** Set a goal weight and a date; the daily calorie and macro targets fall out
 *  of the arithmetic instead of being guessed. */
function GoalCard() {
  const qc = useQueryClient();
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const { data: plan } = useQuery({ queryKey: ["plan"], queryFn: api.plan });

  const [weight, setWeight] = useState("");
  const [date, setDate] = useState("");
  const [auto, setAuto] = useState(false);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (settings && !seeded) {
      setWeight(settings.target_weight_kg ?? "");
      setDate(settings.target_date ?? "");
      setAuto(settings.auto_targets);
      setSeeded(true);
    }
  }, [settings, seeded]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["plan"] });
    qc.invalidateQueries({ queryKey: ["settings"] });
    qc.invalidateQueries({ queryKey: ["day"] });
  };

  const save = useMutation({
    mutationFn: (apply_now) =>
      api.saveGoal({
        target_weight_kg: Number(weight),
        target_date: date,
        auto_targets: auto,
        apply_now,
      }),
    onSuccess: refresh,
  });

  const clear = useMutation({
    mutationFn: api.clearGoal,
    onSuccess: () => {
      setWeight("");
      setDate("");
      setAuto(false);
      refresh();
    },
  });

  const hasGoal = plan?.target_weight != null;
  const losing = (plan?.kg_to_go ?? 0) > 0;

  return (
    <Card title="Goal">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-ink-500">
          Target weight (kg)
          <Input
            type="number"
            step="0.1"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            placeholder="78"
            className="mt-1"
          />
        </label>
        <label className="block text-xs text-ink-500">
          By date
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="mt-1"
          />
        </label>
      </div>

      <label className="mt-3 flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={auto}
          onChange={(e) => setAuto(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-[var(--color-series-1)]"
        />
        <span>
          Auto-adjust my daily targets
          <span className="block text-xs text-ink-500">
            Recomputes every day from your latest weigh-in and the days left, so
            the plan self-corrects instead of going stale.
          </span>
        </span>
      </label>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => save.mutate(false)} disabled={!weight || !date || save.isPending}>
          {save.isPending ? "Saving…" : "Save goal"}
        </Button>
        {hasGoal && !auto && (
          <Button variant="ghost" onClick={() => save.mutate(true)}>
            Apply to my targets
          </Button>
        )}
        {hasGoal && (
          <Button variant="quiet" onClick={() => clear.mutate()}>
            Clear goal
          </Button>
        )}
      </div>

      <ErrorNote>{save.error?.message}</ErrorNote>

      {hasGoal && (
        <div className="mt-4 border-t border-ink-800 pt-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Figure
              label={losing ? "To lose" : "To gain"}
              value={Math.abs(plan.kg_to_go).toFixed(1)}
              unit="kg"
            />
            <Figure label="Days left" value={plan.days_left} unit="" />
            <Figure
              label="Pace"
              value={Math.abs(plan.weekly_rate).toFixed(2)}
              unit="kg/wk"
            />
            <Figure
              label={losing ? "Deficit" : "Surplus"}
              value={Math.abs(plan.daily_delta)}
              unit="kcal/day"
            />
          </div>

          <p className="mt-3 text-sm text-ink-500">
            Maintenance is about{" "}
            <span className="tnum text-ink-100">{plan.maintenance}</span> kcal at{" "}
            {plan.current_weight} kg (desk job — your walking and table tennis are
            counted separately as burn). That gives a target of{" "}
            <span className="tnum text-ink-100">
              {plan.recommended?.daily_calories}
            </span>{" "}
            kcal, {plan.recommended?.protein_g}g protein,{" "}
            {plan.recommended?.carbs_g}g carbs, {plan.recommended?.fat_g}g fat.
          </p>

          {plan.warnings?.map((w) => (
            <p
              key={w}
              className="mt-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn"
            >
              ⚠ {w}
            </p>
          ))}

          {auto && (
            <p className="mt-2 text-xs text-good">
              Auto-adjust is on — the targets below are overridden by this plan.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function Figure({ label, value, unit }) {
  return (
    <div className="rounded-xl bg-ink-850 px-3 py-2">
      <div className="text-[11px] tracking-wide text-ink-500 uppercase">{label}</div>
      <div className="tnum text-lg font-semibold">
        {value}
        {unit && <span className="ml-1 text-xs font-normal text-ink-500">{unit}</span>}
      </div>
    </div>
  );
}

export default function Settings() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const [form, setForm] = useState(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: (payload) => api.saveSettings(payload),
    onSuccess: (fresh) => {
      setForm(fresh);
      qc.invalidateQueries();
    },
  });

  if (isLoading || !form) return <Spinner label="Loading settings" />;

  const set = (key, value) => setForm((f) => ({ ...f, [key]: Number(value) }));

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Settings</h1>

      <GoalCard />

      <Card title="Daily targets">
        <div className="mb-4 flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <Button
              key={preset.label}
              variant="ghost"
              onClick={() => setForm((f) => ({ ...f, ...preset, label: undefined }))}
            >
              {preset.label} · {preset.daily_calories} kcal
            </Button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {TARGETS.map(([key, label, unit]) => (
            <label key={key} className="block text-xs text-ink-500">
              {label} ({unit})
              <Input
                type="number"
                value={form[key]}
                onChange={(e) => set(key, e.target.value)}
                className="mt-1"
              />
            </label>
          ))}
        </div>
      </Card>

      <Card title="Profile">
        <div className="grid gap-3 sm:grid-cols-3">
          {PROFILE.map(([key, label, unit]) => (
            <label key={key} className="block text-xs text-ink-500">
              {label} ({unit})
              <Input
                type="number"
                step={key === "weight_kg" ? "0.1" : "1"}
                value={form[key]}
                onChange={(e) => set(key, e.target.value)}
                className="mt-1"
              />
            </label>
          ))}
        </div>
        <p className="mt-3 text-sm text-ink-500">
          BMR <span className="tnum text-ink-100">{Math.round(form.bmr)}</span> kcal ·
          Maintenance at a desk job{" "}
          <span className="tnum text-ink-100">{Math.round(form.tdee)}</span> kcal.
          Your walking and table tennis are counted on top, from the minutes you log.
        </p>
        <p className="mt-2 text-xs text-ink-500">
          Changing weight here updates future burn calculations. For the trend
          chart, log weigh-ins from the dashboard instead.
        </p>
      </Card>

      <div className="flex items-center gap-3">
        <Button
          onClick={() => {
            const { bmr, tdee, ...payload } = form;
            save.mutate(payload);
          }}
          disabled={save.isPending}
        >
          {save.isPending ? "Saving…" : "Save settings"}
        </Button>
        {save.isSuccess && <span className="text-sm text-good">Saved</span>}
      </div>
      <ErrorNote>{save.error?.message}</ErrorNote>
    </div>
  );
}
