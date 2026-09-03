import { Injectable } from "@nestjs/common";
import { PrismaService } from "../prisma/prisma.service";
import type { AuthenticatedUser } from "../auth/auth.types";
import type { User as PrismaUser } from "@prisma/client";

@Injectable()
export class UsersService {
  constructor(private readonly prisma: PrismaService) {}

  /** Looks up the local User row for a Clerk identity, creating it on first sight. */
  async findOrCreateFromAuth(auth: AuthenticatedUser): Promise<PrismaUser> {
    return this.prisma.user.upsert({
      where: { clerkUserId: auth.clerkUserId },
      update: { email: auth.email, name: auth.name ?? undefined },
      create: {
        clerkUserId: auth.clerkUserId,
        email: auth.email,
        name: auth.name,
      },
    });
  }
}
