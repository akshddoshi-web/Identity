import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { onboardingSchema, type IdentityThreadInput } from "@identity/shared";
import { useIdentityAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { colors } from "../lib/theme";

const EXAMPLES = [
  "I am a disciplined engineer",
  "I am an athlete training for a marathon",
  "I am financially independent by 30",
  "I am becoming a doctor",
];

const MIN_THREADS = 2;
const MAX_THREADS = 4;

export default function OnboardingScreen() {
  const auth = useIdentityAuth();
  const router = useRouter();
  const [threads, setThreads] = useState<IdentityThreadInput[]>([
    { label: "", description: "" },
    { label: "", description: "" },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateThread = (index: number, patch: Partial<IdentityThreadInput>) => {
    setThreads((prev) => prev.map((t, i) => (i === index ? { ...t, ...patch } : t)));
  };

  const addThread = () => {
    if (threads.length >= MAX_THREADS) return;
    setThreads((prev) => [...prev, { label: "", description: "" }]);
  };

  const removeThread = (index: number) => {
    if (threads.length <= MIN_THREADS) return;
    setThreads((prev) => prev.filter((_, i) => i !== index));
  };

  const onSubmit = async () => {
    const cleaned = threads
      .map((t) => ({ label: t.label.trim(), description: t.description?.trim() || undefined }))
      .filter((t) => t.label.length > 0);

    const result = onboardingSchema.safeParse({ threads: cleaned });
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? "Check your threads and try again.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const headers = await auth.authHeaders();
      await api.completeOnboarding(headers, result.data);
      router.replace("/dashboard");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>STEP 1 OF 1</Text>
        <Text style={styles.title}>Define your identity threads</Text>
        <Text style={styles.subtitle}>
          Pick 2 to 4 roles you're becoming — not vague goals, identity statements. Every action you
          log in the app reinforces or contradicts one of these.
        </Text>

        {threads.map((thread, index) => (
          <View key={index} style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardLabel}>Thread {index + 1}</Text>
              {threads.length > MIN_THREADS && (
                <TouchableOpacity onPress={() => removeThread(index)}>
                  <Text style={styles.remove}>Remove</Text>
                </TouchableOpacity>
              )}
            </View>
            <TextInput
              style={styles.input}
              placeholder={EXAMPLES[index % EXAMPLES.length]}
              placeholderTextColor={colors.textMuted}
              value={thread.label}
              onChangeText={(text) => updateThread(index, { label: text })}
            />
            <TextInput
              style={[styles.input, styles.inputMultiline]}
              placeholder="Optional: what does this look like day to day?"
              placeholderTextColor={colors.textMuted}
              value={thread.description}
              onChangeText={(text) => updateThread(index, { description: text })}
              multiline
            />
          </View>
        ))}

        {threads.length < MAX_THREADS && (
          <TouchableOpacity style={styles.addButton} onPress={addThread}>
            <Text style={styles.addButtonText}>+ Add another thread</Text>
          </TouchableOpacity>
        )}

        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity style={styles.button} disabled={submitting} onPress={onSubmit}>
          <Text style={styles.buttonText}>{submitting ? "Saving…" : "Start tracking"}</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 24, paddingTop: 64, paddingBottom: 48 },
  eyebrow: { color: colors.accent, fontWeight: "700", letterSpacing: 3, fontSize: 12, marginBottom: 8 },
  title: { color: colors.text, fontSize: 28, fontWeight: "800", marginBottom: 10 },
  subtitle: { color: colors.textMuted, fontSize: 14, lineHeight: 20, marginBottom: 28 },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  cardLabel: { color: colors.textMuted, fontSize: 12, fontWeight: "700", letterSpacing: 1 },
  remove: { color: colors.bad, fontSize: 13, fontWeight: "600" },
  input: {
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.text,
    fontSize: 15,
    marginBottom: 10,
  },
  inputMultiline: { minHeight: 60, textAlignVertical: "top", marginBottom: 0 },
  addButton: { alignItems: "center", paddingVertical: 14, marginBottom: 8 },
  addButtonText: { color: colors.accent, fontSize: 15, fontWeight: "700" },
  error: { color: colors.bad, marginTop: 8, fontSize: 13 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 20,
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
