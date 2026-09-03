import { Injectable } from "@nestjs/common";
import { PrismaService } from "../prisma/prisma.service";
import { IdentityScoreService } from "./identity-score.service";
import type { OnboardingInput } from "@identity/shared";
import type { DashboardResponse, IdentityScoreSnapshot as IdentityScoreSnapshotDto } from "@identity/shared";
import type { User } from "@prisma/client";

@Injectable()
export class IdentityService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly scoreService: IdentityScoreService,
  ) {}

  async completeOnboarding(userId: string, input: OnboardingInput) {
    const weight = 1 / input.threads.length;
    return this.prisma.$transaction(
      input.threads.map((thread) =>
        this.prisma.identityThread.create({
          data: {
            userId,
            label: thread.label,
            description: thread.description,
            weight,
          },
        }),
      ),
    );
  }

  async getDashboard(user: User): Promise<DashboardResponse> {
    const threads = await this.prisma.identityThread.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "asc" },
    });

    const latest = await this.prisma.identityScoreSnapshot.findFirst({
      where: { userId: user.id },
      orderBy: { date: "desc" },
    });

    if (latest) {
      const snapshot: IdentityScoreSnapshotDto = {
        id: latest.id,
        userId: latest.userId,
        date: latest.date.toISOString(),
        compositeScore: latest.compositeScore,
        threadScores: latest.threadScores as unknown as IdentityScoreSnapshotDto["threadScores"],
      };
      return {
        user: { id: user.id, name: user.name, email: user.email },
        threads: threads.map(this.toThreadDto),
        latestSnapshot: snapshot,
        isZeroState: latest.compositeScore === 0,
      };
    }

    const threadScores = this.scoreService.computeZeroStateScores(threads);
    const compositeScore = this.scoreService.computeComposite(threads, threadScores);

    return {
      user: { id: user.id, name: user.name, email: user.email },
      threads: threads.map(this.toThreadDto),
      latestSnapshot:
        threads.length > 0
          ? {
              id: "zero-state",
              userId: user.id,
              date: new Date().toISOString(),
              compositeScore,
              threadScores,
            }
          : null,
      isZeroState: true,
    };
  }

  private toThreadDto(thread: { id: string; userId: string; label: string; description: string | null; weight: number; createdAt: Date }) {
    return {
      id: thread.id,
      userId: thread.userId,
      label: thread.label,
      description: thread.description,
      weight: thread.weight,
      createdAt: thread.createdAt.toISOString(),
    };
  }
}
