import { z } from "zod";

export const setLogSchema = z.object({
  id: z.string(),
  exerciseName: z.string().min(1),
  setNumber: z.number().int().positive(),
  weightKg: z.number().nonnegative(),
  reps: z.number().int().nonnegative(),
  rpe: z.number().min(1).max(10).nullable(),
  notes: z.string().nullable(),
});
export type SetLog = z.infer<typeof setLogSchema>;

export const workoutSessionSchema = z.object({
  id: z.string(),
  userId: z.string(),
  templateId: z.string().nullable(),
  performedAt: z.coerce.date(),
  sets: z.array(setLogSchema),
});
export type WorkoutSession = z.infer<typeof workoutSessionSchema>;

export const createSetLogInputSchema = setLogSchema.omit({ id: true });
export const createWorkoutSessionInputSchema = workoutSessionSchema
  .omit({ id: true, userId: true, sets: true })
  .extend({ sets: z.array(createSetLogInputSchema) });

export const workoutTemplateSchema = z.object({
  id: z.string(),
  userId: z.string(),
  name: z.string().min(1),
  exercises: z.array(
    z.object({
      exerciseName: z.string().min(1),
      targetSets: z.number().int().positive(),
      targetReps: z.number().int().positive(),
    }),
  ),
});
export type WorkoutTemplate = z.infer<typeof workoutTemplateSchema>;

export interface ExerciseProgressPoint {
  performedAt: Date;
  topSetWeightKg: number;
  estimatedOneRepMaxKg: number;
  totalVolumeKg: number;
}

/** Epley formula — the standard, simplest 1RM estimate from a single set. */
export function estimateOneRepMax(weightKg: number, reps: number): number {
  if (reps <= 0) return 0;
  if (reps === 1) return weightKg;
  return Math.round(weightKg * (1 + reps / 30) * 10) / 10;
}

export function computeExerciseProgression(
  sessions: { performedAt: Date; sets: { exerciseName: string; weightKg: number; reps: number }[] }[],
  exerciseName: string,
): ExerciseProgressPoint[] {
  return sessions
    .map((session) => {
      const sets = session.sets.filter((s) => s.exerciseName === exerciseName);
      if (sets.length === 0) return null;
      const topSetWeightKg = Math.max(...sets.map((s) => s.weightKg));
      const estimatedOneRepMaxKg = Math.max(...sets.map((s) => estimateOneRepMax(s.weightKg, s.reps)));
      const totalVolumeKg = sets.reduce((sum, s) => sum + s.weightKg * s.reps, 0);
      return { performedAt: session.performedAt, topSetWeightKg, estimatedOneRepMaxKg, totalVolumeKg };
    })
    .filter((p): p is ExerciseProgressPoint => p !== null)
    .sort((a, b) => a.performedAt.getTime() - b.performedAt.getTime());
}
