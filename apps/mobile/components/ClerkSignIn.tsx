import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useRouter } from "expo-router";
import { useSignIn, useSignUp } from "@clerk/expo";
import { colors } from "../lib/theme";

type Mode = "sign-in" | "sign-up" | "verify";

/**
 * Clerk email/password sign-in + sign-up, used once EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY is set.
 * Built against Clerk's newer "Future" resource API (signIn.password/signUp.password + finalize),
 * which is what @clerk/expo currently exposes via useSignIn/useSignUp.
 */
export function ClerkSignIn() {
  const router = useRouter();
  const { signIn } = useSignIn();
  const { signUp } = useSignUp();

  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSignIn = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const { error: signInError } = await signIn.password({ identifier: email.trim(), password });
      if (signInError) {
        setError(signInError.message ?? "Sign in failed");
        return;
      }
      const { error: finalizeError } = await signIn.finalize();
      if (finalizeError) {
        setError(finalizeError.message ?? "Sign in failed");
        return;
      }
      router.replace("/");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const onSignUp = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const { error: signUpError } = await signUp.password({ emailAddress: email.trim(), password });
      if (signUpError) {
        setError(signUpError.message ?? "Sign up failed");
        return;
      }
      const { error: sendError } = await signUp.verifications.sendEmailCode();
      if (sendError) {
        setError(sendError.message ?? "Could not send verification code");
        return;
      }
      setMode("verify");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const onVerify = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const { error: verifyError } = await signUp.verifications.verifyEmailCode({ code: code.trim() });
      if (verifyError) {
        setError(verifyError.message ?? "Verification failed");
        return;
      }
      const { error: finalizeError } = await signUp.finalize();
      if (finalizeError) {
        setError(finalizeError.message ?? "Verification failed");
        return;
      }
      router.replace("/");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (mode === "verify") {
    return (
      <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.content}>
          <Text style={styles.eyebrow}>IDENTITY</Text>
          <Text style={styles.title}>Check your email</Text>
          <Text style={styles.subtitle}>Enter the verification code we sent to {email}.</Text>
          <TextInput
            style={styles.input}
            placeholder="123456"
            placeholderTextColor={colors.textMuted}
            value={code}
            onChangeText={setCode}
            keyboardType="number-pad"
          />
          {error && <Text style={styles.error}>{error}</Text>}
          <TouchableOpacity style={styles.button} disabled={submitting} onPress={onVerify}>
            <Text style={styles.buttonText}>{submitting ? "Verifying…" : "Verify"}</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    );
  }

  const isSignIn = mode === "sign-in";

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={styles.content}>
        <Text style={styles.eyebrow}>IDENTITY</Text>
        <Text style={styles.title}>{isSignIn ? "Welcome back" : "Who's becoming who?"}</Text>
        <Text style={styles.subtitle}>
          {isSignIn ? "Sign in to see your threads." : "Create an account to define your identity threads."}
        </Text>

        <Text style={styles.label}>Email</Text>
        <TextInput
          style={styles.input}
          placeholder="jordan@example.com"
          placeholderTextColor={colors.textMuted}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
        />

        <Text style={styles.label}>Password</Text>
        <TextInput
          style={styles.input}
          placeholder="••••••••"
          placeholderTextColor={colors.textMuted}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity style={styles.button} disabled={submitting} onPress={isSignIn ? onSignIn : onSignUp}>
          <Text style={styles.buttonText}>
            {submitting ? "Please wait…" : isSignIn ? "Sign in" : "Create account"}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.switchMode} onPress={() => setMode(isSignIn ? "sign-up" : "sign-in")}>
          <Text style={styles.switchModeText}>
            {isSignIn ? "New here? Create an account" : "Already have an account? Sign in"}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { flex: 1, justifyContent: "center", paddingHorizontal: 28 },
  eyebrow: { color: colors.accent, fontWeight: "700", letterSpacing: 3, fontSize: 12, marginBottom: 8 },
  title: { color: colors.text, fontSize: 30, fontWeight: "800", marginBottom: 10 },
  subtitle: { color: colors.textMuted, fontSize: 14, lineHeight: 20, marginBottom: 28 },
  label: { color: colors.textMuted, fontSize: 13, marginBottom: 6, marginTop: 14 },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: colors.text,
    fontSize: 16,
  },
  error: { color: colors.bad, marginTop: 14, fontSize: 13 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 28,
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  switchMode: { marginTop: 20, alignItems: "center" },
  switchModeText: { color: colors.accent, fontSize: 14, fontWeight: "600" },
});
