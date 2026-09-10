import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const hashedPassword = await bcrypt.hash("password123", 12);

  const user = await prisma.user.upsert({
    where: { email: "demo@identity.local" },
    create: { email: "demo@identity.local", hashedPassword, name: "Demo User" },
    update: {},
  });

  console.log(`Seeded demo user: ${user.email} (password: password123)`);

  await prisma.nutritionProfile.upsert({
    where: { userId: user.id },
    create: {
      userId: user.id,
      sex: "male",
      weightKg: 80,
      heightCm: 180,
      age: 30,
      activityLevel: "moderately_active",
      goal: "maintain",
      proteinPercent: 30,
      carbsPercent: 40,
      fatPercent: 30,
    },
    update: {},
  });

  const chickenBreast = await prisma.food.upsert({
    where: { source_externalId: { source: "custom", externalId: "seed-chicken-breast" } },
    create: {
      source: "custom",
      externalId: "seed-chicken-breast",
      name: "Chicken Breast, Raw",
      caloriesPer100g: 165,
      proteinGPer100g: 31,
      carbsGPer100g: 0,
      fatGPer100g: 3.6,
    },
    update: {},
  });

  const whiteRice = await prisma.food.upsert({
    where: { source_externalId: { source: "custom", externalId: "seed-white-rice" } },
    create: {
      source: "custom",
      externalId: "seed-white-rice",
      name: "White Rice, Cooked",
      caloriesPer100g: 130,
      proteinGPer100g: 2.7,
      carbsGPer100g: 28,
      fatGPer100g: 0.3,
    },
    update: {},
  });

  const broccoli = await prisma.food.upsert({
    where: { source_externalId: { source: "custom", externalId: "seed-broccoli" } },
    create: {
      source: "custom",
      externalId: "seed-broccoli",
      name: "Broccoli, Steamed",
      caloriesPer100g: 35,
      proteinGPer100g: 2.4,
      carbsGPer100g: 7.2,
      fatGPer100g: 0.4,
      fiberGPer100g: 3.3,
    },
    update: {},
  });

  const existingRecipe = await prisma.recipe.findFirst({
    where: { userId: user.id, name: "Chicken, Rice & Broccoli Bowl" },
  });
  if (!existingRecipe) {
    await prisma.recipe.create({
      data: {
        userId: user.id,
        name: "Chicken, Rice & Broccoli Bowl",
        servings: 2,
        ingredients: {
          create: [
            { foodId: chickenBreast.id, grams: 300 },
            { foodId: whiteRice.id, grams: 300 },
            { foodId: broccoli.id, grams: 200 },
          ],
        },
      },
    });
  }

  const template = await prisma.workoutTemplate.findFirst({
    where: { userId: user.id, name: "Push Day A" },
  });
  const pushDay =
    template ??
    (await prisma.workoutTemplate.create({
      data: {
        userId: user.id,
        name: "Push Day A",
        exercises: {
          create: [
            { exerciseName: "Bench Press", targetSets: 4, targetReps: 6, orderIndex: 0 },
            { exerciseName: "Overhead Press", targetSets: 3, targetReps: 8, orderIndex: 1 },
            { exerciseName: "Tricep Pushdown", targetSets: 3, targetReps: 12, orderIndex: 2 },
          ],
        },
      },
    }));

  const today = new Date();
  const existingPlannedLift = await prisma.plannedLift.findFirst({
    where: { userId: user.id, scheduledDate: today },
  });
  if (!existingPlannedLift) {
    await prisma.plannedLift.create({
      data: { userId: user.id, scheduledDate: today, templateId: pushDay.id, label: "Push Day A" },
    });
  }

  console.log("Seed complete.");
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
