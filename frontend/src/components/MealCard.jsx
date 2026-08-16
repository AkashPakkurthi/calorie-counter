import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, UNITS } from "../api.js";
import { Button, Card, ErrorNote, Input, Modal, Select, fmt } from "./ui.jsx";

const NUTRIENTS = [
  ["calories", "kcal"],
  ["protein_g", "P"],
  ["carbs_g", "C"],
  ["fat_g", "F"],
  ["fiber_g", "Fib"],
  ["sugar_g", "Sug"],
  ["sodium_mg", "Na"],
];

export default function MealCard({ meal, date, meals = [] }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState("type");
  const [text, setText] = useState("");
  const [draft, setDraft] = useState(null);
  const [warning, setWarning] = useState(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["day"] });
    qc.invalidateQueries({ queryKey: ["foodOptions"] });
    qc.invalidateQueries({ queryKey: ["favourites"] });
  };

  const analyze = useMutation({
    mutationFn: () => api.analyze(text, meal.key),
    onSuccess: (data) => {
      setDraft(data.items);
      setWarning(data.warning);
    },
  });

  const save = useMutation({
    mutationFn: (items) =>
      api.saveMeal({ date, meal_type: meal.key, raw_text: text, items }),
    onSuccess: () => {
      setDraft(null);
      setText("");
      analyze.reset();
      invalidate();
    },
  });

  const remove = useMutation({
    mutationFn: (id) => api.deleteMeal(id),
    onSuccess: invalidate,
  });

  const items = meals.flatMap((m) => m.items.map((i) => ({ ...i, mealId: m.id })));
  const total = items.reduce((sum, i) => sum + i.calories, 0);

  return (
    <Card
      title={
        <span className="flex items-center gap-2 normal-case">
          <span aria-hidden>{meal.emoji}</span>
          <span className="text-base font-semibold text-ink-100">{meal.label}</span>
        </span>
      }
      action={
        <span className="tnum text-sm text-ink-300">{fmt(total)} kcal</span>
      }
    >
      {items.length > 0 && (
        <ul className="mb-3 divide-y divide-ink-800">
          {items.map((item) => (
            <li key={item.id} className="flex items-center gap-2 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <div className="truncate">
                  {item.name}
                  <span className="ml-1.5 text-ink-500">
                    {item.quantity % 1 === 0 ? item.quantity : item.quantity.toFixed(1)}{" "}
                    {item.unit}
                  </span>
                  {item.from_cache && (
                    <span
                      className="ml-1.5 rounded bg-ink-800 px-1 text-[10px] text-ink-300"
                      title="Resolved from your food cache -- no AI call"
                    >
                      cached
                    </span>
                  )}
                </div>
                <div className="tnum text-xs text-ink-500">
                  P {Math.round(item.protein_g)} · C {Math.round(item.carbs_g)} · F{" "}
                  {Math.round(item.fat_g)} · Fib {Math.round(item.fiber_g)}
                </div>
              </div>
              <span className="tnum shrink-0">{fmt(item.calories)}</span>
              <button
                onClick={() => remove.mutate(item.mealId)}
                className="shrink-0 rounded px-1.5 text-ink-500 hover:bg-ink-800 hover:text-over"
                title="Remove this entry"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mb-2 flex gap-1 rounded-lg bg-ink-850 p-1 text-xs">
        {[
          ["type", "Type it"],
          ["pick", "Pick known food"],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setMode(key)}
            className={`flex-1 rounded-md px-2 py-1.5 transition ${
              mode === key ? "bg-ink-700 text-ink-100" : "text-ink-300 hover:text-ink-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "type" ? (
        <div className="flex gap-2">
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && text.trim()) analyze.mutate();
            }}
            placeholder={`What did you have for ${meal.label.toLowerCase()}?`}
          />
          <Button
            onClick={() => analyze.mutate()}
            disabled={!text.trim() || analyze.isPending}
          >
            {analyze.isPending ? "Thinking…" : "Analyze"}
          </Button>
        </div>
      ) : (
        <PickPanel date={date} mealType={meal.key} onDone={invalidate} />
      )}

      <ErrorNote>{analyze.error?.message || save.error?.message}</ErrorNote>

      <ConfirmModal
        open={!!draft}
        items={draft || []}
        mealLabel={meal.label}
        warning={warning}
        onCancel={() => setDraft(null)}
        onSave={(items) => save.mutate(items)}
        saving={save.isPending}
      />
    </Card>
  );
}

/** Add anything the tracker already knows -- no AI call, no cost. */
function PickPanel({ date, mealType, onDone }) {
  const [q, setQ] = useState("");
  const [picks, setPicks] = useState({});
  const { data: options = [], isLoading } = useQuery({
    queryKey: ["foodOptions"],
    queryFn: () => api.foodOptions(),
  });

  const add = useMutation({
    mutationFn: () =>
      api.pickMeal({
        date,
        meal_type: mealType,
        picks: Object.entries(picks).map(([food_id, quantity]) => ({
          food_id: Number(food_id),
          quantity: Number(quantity) || 1,
        })),
      }),
    onSuccess: () => {
      setPicks({});
      setQ("");
      onDone();
    },
  });

  const filtered = options.filter((o) =>
    `${o.display_name} ${o.normalized_name}`.toLowerCase().includes(q.toLowerCase())
  );
  const chosen = Object.keys(picks).length;

  if (isLoading) return <p className="py-2 text-sm text-ink-500">Loading your foods…</p>;
  if (options.length === 0)
    return (
      <p className="py-2 text-sm text-ink-500">
        No known foods yet — log something with “Type it” first and it lands here
        automatically.
      </p>
    );

  return (
    <div>
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search your foods…"
      />
      <ul className="mt-2 max-h-56 divide-y divide-ink-800 overflow-y-auto rounded-lg border border-ink-800">
        {filtered.map((food) => {
          const picked = picks[food.id] !== undefined;
          return (
            <li
              key={food.id}
              className={`flex items-center gap-2 px-2 py-2 text-sm ${
                picked ? "bg-ink-850" : ""
              }`}
            >
              <button
                className="min-w-0 flex-1 text-left"
                onClick={() =>
                  setPicks((p) => {
                    const next = { ...p };
                    if (picked) delete next[food.id];
                    else next[food.id] = 1;
                    return next;
                  })
                }
              >
                <span className="truncate">{food.display_name}</span>
                <span className="tnum ml-1.5 text-xs text-ink-500">
                  {Math.round(food.calories)} kcal / {food.unit}
                </span>
              </button>
              {picked && (
                <div className="w-20 shrink-0">
                  <Input
                    type="number"
                    min="0.25"
                    step="0.25"
                    value={picks[food.id]}
                    onChange={(e) =>
                      setPicks((p) => ({ ...p, [food.id]: e.target.value }))
                    }
                    className="py-1"
                    aria-label={`Quantity of ${food.display_name}`}
                  />
                </div>
              )}
            </li>
          );
        })}
        {filtered.length === 0 && (
          <li className="px-2 py-3 text-sm text-ink-500">No match.</li>
        )}
      </ul>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-ink-500">
          {chosen ? `${chosen} selected` : "Tap a food to select it"}
        </span>
        <Button onClick={() => add.mutate()} disabled={!chosen || add.isPending}>
          {add.isPending ? "Adding…" : "Add"}
        </Button>
      </div>
      <ErrorNote>{add.error?.message}</ErrorNote>
    </div>
  );
}

/** Nothing is saved until you approve it here -- and every field is editable,
 *  so a correction also teaches the food cache. */
function ConfirmModal({ open, items, mealLabel, warning, onCancel, onSave, saving }) {
  const [rows, setRows] = useState(items);

  // Re-seed when a fresh analysis arrives.
  const [seed, setSeed] = useState(null);
  if (open && seed !== items) {
    setSeed(items);
    setRows(items);
  }

  const update = (idx, field, value) =>
    setRows((r) =>
      r.map((row, i) =>
        i === idx
          ? { ...row, [field]: field === "name" || field === "unit" ? value : Number(value) }
          : row
      )
    );

  const scaleTo = (idx, nextQty) =>
    setRows((r) =>
      r.map((row, i) => {
        if (i !== idx) return row;
        const factor = (Number(nextQty) || 0) / (row.quantity || 1);
        const scaled = Object.fromEntries(
          NUTRIENTS.map(([k]) => [k, Math.round(row[k] * factor * 10) / 10])
        );
        return { ...row, ...scaled, quantity: Number(nextQty) };
      })
    );

  const total = rows.reduce((s, r) => s + (r.calories || 0), 0);

  return (
    <Modal open={open} onClose={onCancel} title={`Confirm ${mealLabel}`} wide>
      <p className="mb-3 text-sm text-ink-500">
        Estimated portions — change anything that looks off. Your edits are
        remembered for next time.
      </p>

      {warning && (
        <p className="mb-3 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          ⚠ {warning}
        </p>
      )}

      <div className="space-y-3">
        {rows.map((row, idx) => (
          <div key={idx} className="rounded-xl border border-ink-800 bg-ink-850 p-3">
            <div className="grid grid-cols-[1fr_4.5rem_6.5rem_auto] items-center gap-2">
              <Input
                value={row.name}
                onChange={(e) => update(idx, "name", e.target.value)}
                aria-label="Food name"
              />
              <Input
                type="number"
                min="0"
                step="0.25"
                value={row.quantity}
                onChange={(e) => scaleTo(idx, e.target.value)}
                aria-label="Quantity"
              />
              <Select
                value={row.unit}
                onChange={(e) => update(idx, "unit", e.target.value)}
                className="w-full"
                aria-label="Unit"
              >
                {UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </Select>
              <Button
                variant="danger"
                onClick={() => setRows((r) => r.filter((_, i) => i !== idx))}
                aria-label="Remove item"
              >
                ✕
              </Button>
            </div>
            <div className="mt-2 grid grid-cols-4 gap-2 sm:grid-cols-7">
              {NUTRIENTS.map(([key, label]) => (
                <label key={key} className="text-[11px] text-ink-500">
                  {label}
                  <Input
                    type="number"
                    step="0.1"
                    value={row[key]}
                    onChange={(e) => update(idx, key, e.target.value)}
                    className="mt-0.5 px-2 py-1 text-xs"
                  />
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <span className="tnum text-sm text-ink-300">Total {fmt(total)} kcal</span>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={() => onSave(rows)} disabled={saving || rows.length === 0}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
