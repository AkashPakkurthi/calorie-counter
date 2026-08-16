import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api.js";
import { Button, Card, ErrorNote, Input, Spinner } from "../components/ui.jsx";

const FIELDS = [
  ["calories", "kcal"],
  ["protein_g", "P"],
  ["carbs_g", "C"],
  ["fat_g", "F"],
  ["fiber_g", "Fib"],
  ["sugar_g", "Sug"],
  ["sodium_mg", "Na"],
];

/** Your learned nutrition cache. Every value here is PER ONE UNIT, and fixing
 *  one fixes every future meal that uses it. */
export default function Foods() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(null);

  const { data: foods = [], isLoading } = useQuery({
    queryKey: ["foods"],
    queryFn: api.foods,
  });

  const update = useMutation({
    mutationFn: ({ id, payload }) => api.updateFood(id, payload),
    onSuccess: () => {
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["foods"] });
      qc.invalidateQueries({ queryKey: ["foodOptions"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id) => api.deleteFood(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["foods"] });
      qc.invalidateQueries({ queryKey: ["foodOptions"] });
    },
  });

  if (isLoading) return <Spinner label="Loading foods" />;

  const filtered = foods.filter((f) =>
    `${f.display_name} ${f.normalized_name}`.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Known foods</h1>
          <p className="text-sm text-ink-500">
            {foods.length} learned · values are per one unit · correcting one here
            fixes it everywhere
          </p>
        </div>
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search…"
          className="max-w-56"
        />
      </div>

      <ErrorNote>{update.error?.message || remove.error?.message}</ErrorNote>

      {filtered.length === 0 ? (
        <Card>
          <p className="py-6 text-center text-sm text-ink-500">
            Nothing here yet. Log a meal and the foods land here automatically.
          </p>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {filtered.map((food) =>
            editing?.id === food.id ? (
              <Card key={food.id}>
                <Input
                  value={editing.display_name}
                  onChange={(e) =>
                    setEditing((f) => ({ ...f, display_name: e.target.value }))
                  }
                />
                <div className="mt-2 grid grid-cols-4 gap-2">
                  {FIELDS.map(([key, label]) => (
                    <label key={key} className="text-[11px] text-ink-500">
                      {label}
                      <Input
                        type="number"
                        step="0.1"
                        value={editing[key]}
                        onChange={(e) =>
                          setEditing((f) => ({ ...f, [key]: Number(e.target.value) }))
                        }
                        className="mt-0.5 px-2 py-1 text-xs"
                      />
                    </label>
                  ))}
                </div>
                <div className="mt-3 flex gap-2">
                  <Button
                    onClick={() =>
                      update.mutate({
                        id: food.id,
                        payload: Object.fromEntries(
                          ["display_name", ...FIELDS.map(([k]) => k)].map((k) => [
                            k,
                            editing[k],
                          ])
                        ),
                      })
                    }
                  >
                    Save
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(null)}>
                    Cancel
                  </Button>
                </div>
              </Card>
            ) : (
              <Card key={food.id}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{food.display_name}</div>
                    <div className="text-xs text-ink-500">
                      per 1 {food.unit} · used {food.hit_count}×
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button variant="quiet" onClick={() => setEditing({ ...food })}>
                      Edit
                    </Button>
                    <Button variant="danger" onClick={() => remove.mutate(food.id)}>
                      ✕
                    </Button>
                  </div>
                </div>
                <div className="tnum mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-300">
                  {FIELDS.map(([key, label]) => (
                    <span key={key}>
                      <span className="text-ink-500">{label}</span>{" "}
                      {Math.round(food[key] * 10) / 10}
                    </span>
                  ))}
                </div>
              </Card>
            )
          )}
        </div>
      )}
    </div>
  );
}
