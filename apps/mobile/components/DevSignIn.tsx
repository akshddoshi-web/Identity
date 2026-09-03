import { useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useRouter } from "expo-router";
import { useIdentityAuth } from "../context/AuthContext";
import { colors } from "../lib/theme";

/**
 * Local dev-mode sign-in, used when EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY isn't set.
 * Mirrors the API's ClerkAuthGuard dev fallback so Phase 0 is demoable without a
 * live Clerk project.
 */
export function DevSignIn() {
  const auth = useIdentityAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = name.trim().length > 0 && /\S+@\S+\.\S+/.test(email.trim());

  const onContinue = async () => {
    if (!canSubmit || !auth.signInLocal) return;
    setSubmitting(true);
    setError(null);
    try {
      await auth.signInLocal(email.trim(), name.trim());
      router.replace("/");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.content}>
        <Text style={styles.eyebrow}>IDENTITY</Text>
        <Text style={styles.title}>Who's becoming who?</Text>
        <Text style={styles.subtitle}>
          No Clerk project is configured yet, so this is dev-mode sign-in — it stores your name
          and email on-device and identifies you to the API the same way a real session would.
        </Text>

        <Text style={styles.label}>Name</Text>
        <TextInput
          style={styles.input}
          placeholder="Jordan Rivera"
          placeholderTextColor={colors.textMuted}
          value={name}
          onChangeText={setName}
          autoCapitalize="words"
        />

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

        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity
          style={[styles.button, !canSubmit && styles.buttonDisabled]}
          disabled={!canSubmit || submitting}
          onPress={onContinue}
        >
          <Text style={styles.buttonText}>{submitting ? "Continuing…" : "Continue"}</Text>
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
  buttonDisabled: { opacity: 0.4 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
