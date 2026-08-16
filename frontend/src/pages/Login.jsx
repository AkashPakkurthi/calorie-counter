import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { api } from "../api.js";
import { Button, Card, ErrorNote, Input, Select } from "../components/ui.jsx";

const CM_PER_INCH = 2.54;

/** Height is entered in whichever unit you think in; centimetres are what the
 *  formulas need, so feet/inches are converted on the way in. */
function HeightField({ unit, setUnit, cm, setCm, feet, setFeet, inches, setInches }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs text-ink-500">Height</span>
        <div className="flex gap-1 rounded-lg bg-ink-850 p-0.5 text-xs">
          {["cm", "ft"].map((u) => (
            <button
              key={u}
              type="button"
              onClick={() => setUnit(u)}
              className={`rounded px-2 py-0.5 ${
                unit === u ? "bg-ink-700 text-ink-100" : "text-ink-500"
              }`}
            >
              {u === "cm" ? "cm" : "ft / in"}
            </button>
          ))}
        </div>
      </div>
      {unit === "cm" ? (
        <Input
          type="number"
          step="0.5"
          value={cm}
          onChange={(e) => setCm(e.target.value)}
          placeholder="178"
          aria-label="Height in centimetres"
        />
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            value={feet}
            onChange={(e) => setFeet(e.target.value)}
            placeholder="5 ft"
            aria-label="Height feet"
          />
          <Input
            type="number"
            value={inches}
            onChange={(e) => setInches(e.target.value)}
            placeholder="10 in"
            aria-label="Height inches"
          />
        </div>
      )}
    </div>
  );
}

export default function Login() {
  const [params] = useSearchParams();
  const [mode, setMode] = useState(params.get("invite") ? "register" : "login");

  const { data: config } = useQuery({ queryKey: ["authConfig"], queryFn: api.authConfig });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [invite, setInvite] = useState(params.get("invite") || "");
  const [sex, setSex] = useState("male");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [heightUnit, setHeightUnit] = useState("cm");
  const [cm, setCm] = useState("");
  const [feet, setFeet] = useState("");
  const [inches, setInches] = useState("");

  const heightCm =
    heightUnit === "cm"
      ? Number(cm)
      : Math.round((Number(feet) * 12 + Number(inches)) * CM_PER_INCH * 10) / 10;

  const submit = useMutation({
    mutationFn: () =>
      mode === "login"
        ? api.login(email, password)
        : api.register({
            email,
            password,
            name,
            invite_code: invite,
            sex,
            age: Number(age),
            height_cm: heightCm,
            weight_kg: Number(weight),
          }),
    onSuccess: () => {
      // Reload rather than patching the cache: the session cookie is already
      // set, so a fresh boot picks it up with no chance of the old account's
      // data or the previous 401 lingering in memory.
      window.location.assign("/");
    },
  });

  const registering = mode === "register";
  const ready =
    email &&
    password &&
    (!registering || (age && weight && heightCm > 100 && heightCm < 250));

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <div className="mb-6 text-center">
        <div className="text-3xl">🔥</div>
        <h1 className="mt-2 text-2xl font-semibold">Calorie Tracker</h1>
        <p className="mt-1 text-sm text-ink-500">
          {registering
            ? "A few details so the calculations fit you."
            : "Sign in to your food log."}
        </p>
      </div>

      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (ready) submit.mutate();
          }}
          className="space-y-3"
        >
          <label className="block text-xs text-ink-500">
            Email
            <Input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1"
              required
            />
          </label>

          <label className="block text-xs text-ink-500">
            Password
            <Input
              type="password"
              autoComplete={registering ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1"
              required
              minLength={registering ? 8 : undefined}
            />
            {registering && (
              <span className="mt-1 block text-[11px] text-ink-500">
                At least 8 characters.
              </span>
            )}
          </label>

          {registering && (
            <>
              <label className="block text-xs text-ink-500">
                Name
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Akash"
                  className="mt-1"
                />
              </label>

              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs text-ink-500">
                  Gender
                  <Select
                    value={sex}
                    onChange={(e) => setSex(e.target.value)}
                    className="mt-1 w-full"
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </Select>
                  <span className="mt-1 block text-[11px] text-ink-500">
                    Changes the BMR formula.
                  </span>
                </label>
                <label className="block text-xs text-ink-500">
                  Age
                  <Input
                    type="number"
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                    placeholder="26"
                    className="mt-1"
                    required
                  />
                </label>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <HeightField
                  {...{
                    unit: heightUnit,
                    setUnit: setHeightUnit,
                    cm,
                    setCm,
                    feet,
                    setFeet,
                    inches,
                    setInches,
                  }}
                />
                <label className="block text-xs text-ink-500">
                  Weight (kg)
                  <Input
                    type="number"
                    step="0.1"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    placeholder="86"
                    className="mt-1"
                    required
                  />
                </label>
              </div>

              {heightUnit === "ft" && heightCm > 0 && (
                <p className="text-[11px] text-ink-500">= {heightCm} cm</p>
              )}

              {config?.invite_required && (
                <label className="block text-xs text-ink-500">
                  Invite code
                  <Input
                    value={invite}
                    onChange={(e) => setInvite(e.target.value)}
                    className="mt-1"
                    required
                  />
                </label>
              )}
            </>
          )}

          <Button type="submit" disabled={!ready || submit.isPending} className="w-full">
            {submit.isPending
              ? "Just a moment…"
              : registering
                ? "Create account"
                : "Sign in"}
          </Button>
        </form>

        <ErrorNote>{submit.error?.message}</ErrorNote>

        <p className="mt-4 text-center text-sm text-ink-500">
          {registering ? "Already have an account?" : "First time here?"}{" "}
          <button
            className="text-series-1 hover:underline"
            onClick={() => {
              submit.reset();
              setMode(registering ? "login" : "register");
            }}
          >
            {registering ? "Sign in" : "Create an account"}
          </button>
        </p>
      </Card>

      {registering && (
        <p className="mt-4 text-center text-xs text-ink-500">
          You can set a target weight and date from Settings once you're in.
        </p>
      )}
    </div>
  );
}
