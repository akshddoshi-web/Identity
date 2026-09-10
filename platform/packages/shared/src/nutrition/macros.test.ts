import { describe, expect, it } from "vitest";
import {
  calculateRecipeMacros,
  estimateCaloriesFromMacros,
  macroTargetsFromSplit,
  sumDailyMacros,
} from "./macros";

describe("estimateCaloriesFromMacros", () => {
  it("applies the Atwater 4/4/9 factors", () => {
    expect(estimateCaloriesFromMacros({ proteinG: 20, carbsG: 30, fatG: 10 })).toBe(
      20 * 4 + 30 * 4 + 10 * 9,
    );
  });
});

describe("calculateRecipeMacros", () => {
  it("scales per-100g ingredient macros by grams and sums the recipe", () => {
    // 200g chicken breast (per 100g: 165 kcal, 31p, 0c, 3.6f) + 150g rice (per 100g: 130 kcal, 2.7p, 28c, 0.3f)
    const { total } = calculateRecipeMacros(
      [
        { per100g: { calories: 165, proteinG: 31, carbsG: 0, fatG: 3.6 }, grams: 200 },
        { per100g: { calories: 130, proteinG: 2.7, carbsG: 28, fatG: 0.3 }, grams: 150 },
      ],
      1,
    );
    expect(total.calories).toBe(Math.round(165 * 2 + 130 * 1.5));
    expect(total.proteinG).toBeCloseTo(31 * 2 + 2.7 * 1.5, 1);
  });

  it("divides the total evenly across servings", () => {
    const { total, perServing } = calculateRecipeMacros(
      [{ per100g: { calories: 200, proteinG: 20, carbsG: 10, fatG: 5 }, grams: 400 }],
      4,
    );
    expect(total.calories).toBe(800);
    expect(perServing.calories).toBe(200);
    expect(perServing.proteinG).toBeCloseTo(20, 1);
  });

  it("rejects zero or negative servings", () => {
    expect(() =>
      calculateRecipeMacros([{ per100g: { calories: 100, proteinG: 1, carbsG: 1, fatG: 1 }, grams: 100 }], 0),
    ).toThrow();
  });

  it("preserves optional micronutrients through scaling", () => {
    const { total } = calculateRecipeMacros(
      [
        {
          per100g: { calories: 50, proteinG: 1, carbsG: 10, fatG: 0, fiberG: 2, sugarG: 5, sodiumMg: 10 },
          grams: 200,
        },
      ],
      1,
    );
    expect(total.fiberG).toBeCloseTo(4, 1);
    expect(total.sugarG).toBeCloseTo(10, 1);
    expect(total.sodiumMg).toBe(20);
  });
});

describe("sumDailyMacros", () => {
  it("rolls up multiple logged entries", () => {
    const result = sumDailyMacros([
      { macros: { calories: 500, proteinG: 30, carbsG: 50, fatG: 15 } },
      { macros: { calories: 300, proteinG: 20, carbsG: 20, fatG: 10 } },
    ]);
    expect(result.calories).toBe(800);
    expect(result.proteinG).toBe(50);
  });
});

describe("macroTargetsFromSplit", () => {
  it("converts a calorie target + percentage split into gram targets", () => {
    const targets = macroTargetsFromSplit(2000, {
      proteinPercent: 30,
      carbsPercent: 40,
      fatPercent: 30,
    });
    expect(targets.calories).toBe(2000);
    expect(targets.proteinG).toBe(Math.round((2000 * 0.3) / 4));
    expect(targets.carbsG).toBe(Math.round((2000 * 0.4) / 4));
    expect(targets.fatG).toBe(Math.round((2000 * 0.3) / 9));
  });

  it("rejects a split that doesn't sum to 100%", () => {
    expect(() =>
      macroTargetsFromSplit(2000, { proteinPercent: 30, carbsPercent: 30, fatPercent: 30 }),
    ).toThrow();
  });
});
