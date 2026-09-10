"use client";

import { useState } from "react";
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { trpc } from "@/lib/trpc/client";

export default function TrainingPage() {
  const utils = trpc.useUtils();
  const templates = trpc.training.listTemplates.useQuery();
  const sessions = trpc.training.listSessions.useQuery();

  const [templateName, setTemplateName] = useState("");
  const [templateExercises, setTemplateExercises] = useState<{ exerciseName: string; targetSets: string; targetReps: string }[]>([
    { exerciseName: "", targetSets: "3", targetReps: "8" },
  ]);
  const createTemplate = trpc.training.createTemplate.useMutation({
    onSuccess: () => {
      utils.training.listTemplates.invalidate();
      setTemplateName("");
      setTemplateExercises([{ exerciseName: "", targetSets: "3", targetReps: "8" }]);
    },
  });

  const [sets, setSets] = useState<{ exerciseName: string; weightKg: string; reps: string }[]>([
    { exerciseName: "", weightKg: "", reps: "" },
  ]);
  const logSession = trpc.training.logSession.useMutation({
    onSuccess: () => {
      utils.training.listSessions.invalidate();
      setSets([{ exerciseName: "", weightKg: "", reps: "" }]);
    },
  });

  const [progressExercise, setProgressExercise] = useState("");
  const progression = trpc.training.exerciseProgression.useQuery(
    { exerciseName: progressExercise },
    { enabled: progressExercise.length > 0 },
  );

  return (
    <div className="space-y-8">
      <h1 className="text-2xl">Training</h1>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Workout templates</h2>
        <div className="space-y-2">
          {templates.data?.map((template) => (
            <div key={template.id} className="text-sm">
              <span className="text-ink-100">{template.name}</span>
              <span className="ml-2 text-ink-500">
                {template.exercises.map((e) => `${e.exerciseName} ${e.targetSets}x${e.targetReps}`).join(", ")}
              </span>
            </div>
          ))}
        </div>
        <input className="input" placeholder="Template name" value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
        {templateExercises.map((ex, i) => (
          <div key={i} className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Exercise"
              value={ex.exerciseName}
              onChange={(e) =>
                setTemplateExercises((exs) => exs.map((x, idx) => (idx === i ? { ...x, exerciseName: e.target.value } : x)))
              }
            />
            <input
              className="input w-20"
              placeholder="Sets"
              type="number"
              value={ex.targetSets}
              onChange={(e) => setTemplateExercises((exs) => exs.map((x, idx) => (idx === i ? { ...x, targetSets: e.target.value } : x)))}
            />
            <input
              className="input w-20"
              placeholder="Reps"
              type="number"
              value={ex.targetReps}
              onChange={(e) => setTemplateExercises((exs) => exs.map((x, idx) => (idx === i ? { ...x, targetReps: e.target.value } : x)))}
            />
          </div>
        ))}
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setTemplateExercises((exs) => [...exs, { exerciseName: "", targetSets: "3", targetReps: "8" }])}>
            + Add exercise
          </button>
          <button
            className="btn-primary"
            disabled={!templateName || createTemplate.isPending}
            onClick={() =>
              createTemplate.mutate({
                name: templateName,
                exercises: templateExercises
                  .filter((e) => e.exerciseName)
                  .map((e) => ({ exerciseName: e.exerciseName, targetSets: Number(e.targetSets), targetReps: Number(e.targetReps) })),
              })
            }
          >
            Save template
          </button>
        </div>
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Log a session</h2>
        {sets.map((set, i) => (
          <div key={i} className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Exercise"
              value={set.exerciseName}
              onChange={(e) => setSets((s) => s.map((x, idx) => (idx === i ? { ...x, exerciseName: e.target.value } : x)))}
            />
            <input
              className="input w-24"
              placeholder="Weight kg"
              type="number"
              value={set.weightKg}
              onChange={(e) => setSets((s) => s.map((x, idx) => (idx === i ? { ...x, weightKg: e.target.value } : x)))}
            />
            <input
              className="input w-20"
              placeholder="Reps"
              type="number"
              value={set.reps}
              onChange={(e) => setSets((s) => s.map((x, idx) => (idx === i ? { ...x, reps: e.target.value } : x)))}
            />
          </div>
        ))}
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setSets((s) => [...s, { exerciseName: "", weightKg: "", reps: "" }])}>
            + Add set
          </button>
          <button
            className="btn-primary"
            disabled={logSession.isPending}
            onClick={() =>
              logSession.mutate({
                performedAt: new Date(),
                templateId: null,
                sets: sets
                  .filter((s) => s.exerciseName)
                  .map((s, idx) => ({
                    exerciseName: s.exerciseName,
                    setNumber: idx + 1,
                    weightKg: Number(s.weightKg),
                    reps: Number(s.reps),
                    rpe: null,
                    notes: null,
                  })),
              })
            }
          >
            Log session
          </button>
        </div>
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="text-lg">Exercise progression</h2>
        <input className="input" placeholder="Exercise name (exact match)" value={progressExercise} onChange={(e) => setProgressExercise(e.target.value)} />
        {progression.data && progression.data.length > 1 && (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart
              data={progression.data.map((p) => ({
                date: new Date(p.performedAt).toLocaleDateString(),
                estimatedOneRepMaxKg: p.estimatedOneRepMaxKg,
              }))}
            >
              <XAxis dataKey="date" stroke="#7c8f8c" fontSize={12} />
              <YAxis stroke="#7c8f8c" fontSize={12} domain={["auto", "auto"]} />
              <Tooltip contentStyle={{ background: "#1a2224", border: "1px solid #26302f" }} />
              <Line type="monotone" dataKey="estimatedOneRepMaxKg" stroke="#e2600f" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      <section className="panel space-y-2 p-5">
        <h2 className="text-lg">Recent sessions</h2>
        {sessions.data?.slice(0, 5).map((session) => (
          <div key={session.id} className="text-sm text-ink-300">
            {new Date(session.performedAt).toLocaleDateString()} —{" "}
            {session.sets.map((s) => `${s.exerciseName} ${s.weightKg}kg x${s.reps}`).join(", ")}
          </div>
        ))}
      </section>
    </div>
  );
}
