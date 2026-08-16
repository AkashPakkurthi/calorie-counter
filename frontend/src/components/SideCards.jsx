import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api.js";
import { Button, Card, ErrorNote, Input, fmt } from "./ui.jsx";

/** Walking + table tennis, priced per minute from your current weight.
 *  No AI call -- this is straight MET arithmetic. */
export function ActivityCard({ date, activity }) {
  const qc = useQueryClient();
  const [walking, setWalking] = useState(activity.walking_min);
  const [tt, setTt] = useState(activity.tt_min);

  const { data: rates } = useQuery({
    queryKey: ["activityRates"],
    queryFn: api.activityRates,
  });

  const save = useMutation({
    mutationFn: () =>
      api.saveActivity(date, {
        walking_min: Number(walking) || 0,
        tt_min: Number(tt) || 0,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["day"] }),
  });

  const dirty =
    Number(walking) !== activity.walking_min || Number(tt) !== activity.tt_min;

  return (
    <Card
      title="Exercise"
      action={
        <span className="tnum text-sm text-series-3">
          {fmt(activity.calories_burned)} kcal
        </span>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <Field
          label="Walking"
          value={walking}
          onChange={setWalking}
          hint={rates ? `${rates.walking_kcal_per_min} kcal/min` : ""}
        />
        <Field
          label="Table tennis"
          value={tt}
          onChange={setTt}
          hint={rates ? `${rates.tt_kcal_per_min} kcal/min` : ""}
        />
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-ink-500">
          at {activity.weight_used_kg} kg
        </span>
        <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
      </div>
      <ErrorNote>{save.error?.message}</ErrorNote>
    </Card>
  );
}

function Field({ label, value, onChange, hint }) {
  return (
    <label className="block text-xs text-ink-500">
      {label} <span className="text-ink-500">(min)</span>
      <Input
        type="number"
        min="0"
        step="5"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1"
      />
      {hint && <span className="mt-1 block text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}

export function WaterCard({ date, water, target }) {
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: (ml) => api.saveWater(date, Math.max(ml, 0)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["day"] }),
  });
  const glasses = Math.round(water.ml / 250);
  const targetGlasses = Math.round(target / 250);

  return (
    <Card
      title="Water"
      action={
        <span className="tnum text-sm text-ink-300">
          {(water.ml / 1000).toFixed(1)} / {(target / 1000).toFixed(1)} L
        </span>
      }
    >
      <div className="flex flex-wrap gap-1.5">
        {Array.from({ length: Math.max(targetGlasses, glasses) }).map((_, i) => (
          <button
            key={i}
            onClick={() => save.mutate((i + 1) * 250)}
            title={`${(i + 1) * 250} ml`}
            className={`h-7 w-5 rounded-sm border transition ${
              i < glasses
                ? "border-series-1 bg-series-1"
                : "border-field bg-ink-850 hover:border-ink-300"
            }`}
          />
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Button variant="ghost" onClick={() => save.mutate(water.ml + 250)}>
          +250 ml
        </Button>
        <Button variant="quiet" onClick={() => save.mutate(0)}>
          Reset
        </Button>
      </div>
    </Card>
  );
}

/** Weekly weigh-in. Past days keep the weight they were logged under. */
export function WeightCard({ currentWeight, staleDays }) {
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const { data: weights = [] } = useQuery({ queryKey: ["weights"], queryFn: api.weights });

  const log = useMutation({
    mutationFn: () => api.logWeight(Number(value)),
    onSuccess: () => {
      setValue("");
      qc.invalidateQueries({ queryKey: ["weights"] });
      qc.invalidateQueries({ queryKey: ["day"] });
      qc.invalidateQueries({ queryKey: ["activityRates"] });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const { data: plan } = useQuery({ queryKey: ["plan"], queryFn: api.plan });

  const [latest, previous] = weights;
  const delta = latest && previous ? latest.weight_kg - previous.weight_kg : null;
  const nudge = staleDays === null || staleDays === undefined || staleDays > 7;

  return (
    <Card
      title="Weight"
      action={
        delta !== null && (
          <span
            className={`tnum text-sm ${delta <= 0 ? "text-good" : "text-warn"}`}
            title={`vs ${previous.date}`}
          >
            {delta > 0 ? "+" : ""}
            {delta.toFixed(1)} kg
          </span>
        )
      }
    >
      <div className="tnum text-3xl font-semibold">
        {currentWeight?.toFixed(1)}
        <span className="ml-1 text-base font-normal text-ink-500">kg</span>
      </div>
      <p className="mt-1 text-xs text-ink-500">
        {latest ? `Last weighed ${latest.date}` : "No weigh-in logged yet"}
      </p>

      {plan?.target_weight != null && plan.days_left > 0 && (
        <div className="mt-2">
          <div className="mb-1 flex justify-between text-xs text-ink-500">
            <span>
              {Math.abs(plan.kg_to_go).toFixed(1)} kg to {plan.target_weight} kg
            </span>
            <span className="tnum">{plan.days_left} days left</span>
          </div>
          <div
            className="h-1.5 overflow-hidden rounded-full bg-ink-800"
            role="progressbar"
            aria-valuenow={plan.progress_pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Progress from ${plan.start_weight} kg to ${plan.target_weight} kg`}
          >
            <div
              className="h-full rounded-full bg-series-1 transition-[width] duration-500"
              style={{ width: `${plan.progress_pct}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-ink-500">
            {plan.progress_pct}% there, from {plan.start_weight} kg
          </p>
        </div>
      )}
      {nudge && (
        <p className="mt-2 rounded-lg bg-ink-850 px-3 py-2 text-xs text-warn">
          Time for a weigh-in — it keeps your burn numbers honest.
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <Input
          type="number"
          step="0.1"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="86.0"
        />
        <Button onClick={() => log.mutate()} disabled={!value || log.isPending}>
          Log
        </Button>
      </div>
      <ErrorNote>{log.error?.message}</ErrorNote>
    </Card>
  );
}

export function FavouritesStrip({ date }) {
  const qc = useQueryClient();
  const { data: favourites = [] } = useQuery({
    queryKey: ["favourites"],
    queryFn: api.favourites,
  });

  const log = useMutation({
    mutationFn: (id) => api.logFavourite(id, { date }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["day"] }),
  });

  const remove = useMutation({
    mutationFn: (id) => api.deleteFavourite(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favourites"] }),
  });

  if (favourites.length === 0) return null;

  return (
    <Card title="Favourites">
      <div className="flex flex-wrap gap-2">
        {favourites.map((fav) => (
          <span
            key={fav.id}
            className="group flex items-center gap-1 rounded-full border border-field bg-ink-850 pr-1 pl-3 text-sm"
          >
            <button
              onClick={() => log.mutate(fav.id)}
              className="py-1.5"
              title={`Add to ${fav.meal_type}`}
            >
              {fav.label}
              <span className="tnum ml-1.5 text-xs text-ink-500">
                {fmt(fav.total_calories)}
              </span>
            </button>
            <button
              onClick={() => remove.mutate(fav.id)}
              className="rounded-full px-1.5 text-ink-500 hover:text-over"
              title="Delete favourite"
            >
              ✕
            </button>
          </span>
        ))}
      </div>
    </Card>
  );
}
