import { z } from "zod";
import { computeExerciseProgression, createWorkoutSessionInputSchema, workoutTemplateSchema } from "@identity/shared";
import { protectedProcedure, router } from "../trpc";

export const trainingRouter = router({
  createTemplate: protectedProcedure
    .input(workoutTemplateSchema.omit({ id: true, userId: true }))
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.workoutTemplate.create({
        data: {
          userId: ctx.userId,
          name: input.name,
          exercises: {
            create: input.exercises.map((e, i) => ({
              exerciseName: e.exerciseName,
              targetSets: e.targetSets,
              targetReps: e.targetReps,
              orderIndex: i,
            })),
          },
        },
        include: { exercises: true },
      });
    }),

  listTemplates: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.workoutTemplate.findMany({
      where: { userId: ctx.userId },
      include: { exercises: { orderBy: { orderIndex: "asc" } } },
    });
  }),

  logSession: protectedProcedure.input(createWorkoutSessionInputSchema).mutation(async ({ ctx, input }) => {
    return ctx.prisma.workoutSession.create({
      data: {
        userId: ctx.userId,
        templateId: input.templateId,
        performedAt: input.performedAt,
        sets: {
          create: input.sets.map((s) => ({
            exerciseName: s.exerciseName,
            setNumber: s.setNumber,
            weightKg: s.weightKg,
            reps: s.reps,
            rpe: s.rpe,
            notes: s.notes,
          })),
        },
      },
      include: { sets: true },
    });
  }),

  listSessions: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.workoutSession.findMany({
      where: { userId: ctx.userId },
      include: { sets: true },
      orderBy: { performedAt: "desc" },
    });
  }),

  exerciseProgression: protectedProcedure
    .input(z.object({ exerciseName: z.string().min(1) }))
    .query(async ({ ctx, input }) => {
      const sessions = await ctx.prisma.workoutSession.findMany({
        where: { userId: ctx.userId },
        include: { sets: true },
      });
      return computeExerciseProgression(sessions, input.exerciseName);
    }),
});
