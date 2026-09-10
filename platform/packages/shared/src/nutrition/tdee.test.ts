import { describe, expect, it } from "vitest";
import {
  calculateAutoCalorieTarget,
  calculateBmr,
  calculateCalorieTarget,
  calculateTdee,
} from "./tdee";

describe("calculateBmr (Mifflin-St Jeor)", () => {
  it("matches the textbook formula for a male", () => {
    // 80kg, 180cm, 30yo male: 10*80 + 6.25*180 - 5*30 + 5 = 800+1125-150+5 = 1780
    expect(calculateBmr({ sex: "male", weightKg: 80, heightCm: 180, age: 30 })).toBe(1780);
  });

  it("matches the textbook formula for a female", () => {
    // 65kg, 165cm, 28yo female: 10*65+6.25*165-5*28-161 = 650+1031.25-140-161 = 1380.25 -> 1380
    expect(calculateBmr({ sex: "female", weightKg: 65, heightCm: 165, age: 28 })).toBe(1380);
  });
});

describe("calculateTdee", () => {
  it("applies the activity multiplier", () => {
    expect(calculateTdee(1780, "sedentary")).toBe(Math.round(1780 * 1.2));
    expect(calculateTdee(1780, "very_active")).toBe(Math.round(1780 * 1.725));
  });
});

describe("calculateCalorieTarget", () => {
  it("subtracts the deficit for a weight-loss goal", () => {
    expect(calculateCalorieTarget(2500, "lose")).toBe(2000);
  });
  it("adds the surplus for a weight-gain goal", () => {
    expect(calculateCalorieTarget(2500, "gain")).toBe(3000);
  });
  it("leaves TDEE unchanged for maintenance", () => {
    expect(calculateCalorieTarget(2500, "maintain")).toBe(2500);
  });
  it("honors a custom adjustment", () => {
    expect(calculateCalorieTarget(2500, "lose", 250)).toBe(2250);
  });
});

describe("calculateAutoCalorieTarget", () => {
  it("chains BMR -> TDEE -> goal target", () => {
    const result = calculateAutoCalorieTarget({
      sex: "male",
      weightKg: 80,
      heightCm: 180,
      age: 30,
      activityLevel: "moderately_active",
      goal: "lose",
    });
    expect(result.bmr).toBe(1780);
    expect(result.tdee).toBe(Math.round(1780 * 1.55));
    expect(result.calorieTarget).toBe(result.tdee - 500);
  });
});
