import { Body, Controller, Get, Post, UseGuards } from "@nestjs/common";
import { ClerkAuthGuard } from "../auth/clerk-auth.guard";
import { CurrentUser } from "../auth/current-user.decorator";
import { UsersService } from "../users/users.service";
import { IdentityService } from "./identity.service";
import { ZodValidationPipe } from "../common/zod-validation.pipe";
import { onboardingSchema, type OnboardingInput } from "@identity/shared";
import type { AuthenticatedUser } from "../auth/auth.types";

@Controller("identity")
@UseGuards(ClerkAuthGuard)
export class IdentityController {
  constructor(
    private readonly identityService: IdentityService,
    private readonly usersService: UsersService,
  ) {}

  @Post("onboarding")
  async completeOnboarding(
    @CurrentUser() auth: AuthenticatedUser,
    @Body(new ZodValidationPipe(onboardingSchema)) body: OnboardingInput,
  ) {
    const user = await this.usersService.findOrCreateFromAuth(auth);
    const threads = await this.identityService.completeOnboarding(user.id, body);
    return { threads };
  }

  @Get("dashboard")
  async getDashboard(@CurrentUser() auth: AuthenticatedUser) {
    const user = await this.usersService.findOrCreateFromAuth(auth);
    return this.identityService.getDashboard(user);
  }
}
