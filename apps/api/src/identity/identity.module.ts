import { Module } from "@nestjs/common";
import { IdentityController } from "./identity.controller";
import { IdentityService } from "./identity.service";
import { IdentityScoreService } from "./identity-score.service";
import { UsersModule } from "../users/users.module";
import { AuthModule } from "../auth/auth.module";

@Module({
  imports: [UsersModule, AuthModule],
  controllers: [IdentityController],
  providers: [IdentityService, IdentityScoreService],
})
export class IdentityModule {}
