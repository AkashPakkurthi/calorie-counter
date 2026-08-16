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
          Maintenance (light activity){" "}
          <span className="tnum text-ink-100">{Math.round(form.tdee)}</span> kcal.
          Exercise burn is counted separately from your logged minutes.
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
