import { isClerkConfigured } from "../context/AuthContext";
import { ClerkSignIn } from "../components/ClerkSignIn";
import { DevSignIn } from "../components/DevSignIn";

export default function SignInScreen() {
  return isClerkConfigured ? <ClerkSignIn /> : <DevSignIn />;
}
