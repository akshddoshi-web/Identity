import { describe, expect, it } from "vitest";
import { computeExerciseProgression, estimateOneRepMax } from "./training";

describe("estimateOneRepMax (Epley)", () => {
  it("returns the weight itself for a single rep", () => {
    expect(estimateOneRepMax(100, 1)).toBe(100);
  });

  it("estimates a higher 1RM for more reps at the same weight", () => {
    expect(estimateOneRepMax(100, 5)).toBeCloseTo(100 * (1 + 5 / 30), 1);
  });

  it("returns 0 for zero reps", () => {
    expect(estimateOneRepMax(100, 0)).toBe(0);
  });
});

describe("computeExerciseProgression", () => {
  it("tracks top set, estimated 1RM, and volume per session, sorted chronologically", () => {
    const sessions = [
      {
        performedAt: new Date("2024-02-01"),
        sets: [
          { exerciseName: "Squat", weightKg: 120, reps: 5 },
          { exerciseName: "Bench", weightKg: 80, reps: 5 },
        ],
      },
      {
        performedAt: new Date("2024-01-01"),
        sets: [{ exerciseName: "Squat", weightKg: 100, reps: 5 }],
      },
    ];
    const progression = computeExerciseProgression(sessions, "Squat");
    expect(progression).toHaveLength(2);
    expect(progression[0].performedAt).toEqual(new Date("2024-01-01"));
    expect(progression[1].topSetWeightKg).toBe(120);
    expect(progression[1].totalVolumeKg).toBe(600);
  });

  it("ignores sessions with no matching exercise", () => {
    const sessions = [
      { performedAt: new Date("2024-01-01"), sets: [{ exerciseName: "Deadlift", weightKg: 150, reps: 3 }] },
    ];
    expect(computeExerciseProgression(sessions, "Squat")).toEqual([]);
  });
});
