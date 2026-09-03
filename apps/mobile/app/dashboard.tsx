import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import type { DashboardResponse } from "@identity/shared";
import { useIdentityAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { colors } from "../lib/theme";
import { IdentityScoreRing } from "../components/IdentityScoreRing";
import { ThreadCard } from "../components/ThreadCard";

export default function DashboardScreen() {
  const auth = useIdentityAuth();
  const router = useRouter();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const headers = await auth.authHeaders();
      const dashboard = await api.getDashboard(headers);
      setData(dashboard);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [auth]);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const onSignOut = async () => {
    await auth.signOut();
    router.replace("/sign-in");
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator size="large" color={colors.accent} />
      </SafeAreaView>
    );
  }

  const compositeScore = data?.latestSnapshot?.compositeScore ?? 0;
  const threadScores = data?.latestSnapshot?.threadScores ?? [];

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl tintColor={colors.accent} refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Hey{data?.user.name ? `, ${data.user.name.split(" ")[0]}` : ""}</Text>
            <Text style={styles.subGreeting}>Here's who you're becoming</Text>
          </View>
          <TouchableOpacity onPress={onSignOut}>
            <Text style={styles.signOut}>Sign out</Text>
          </TouchableOpacity>
        </View>

        {error && <Text style={styles.error}>{error}</Text>}

        <View style={styles.ringWrap}>
          <IdentityScoreRing score={compositeScore} isZeroState={data?.isZeroState ?? true} />
        </View>

        {data?.isZeroState && (
          <View style={styles.zeroStateNote}>
            <Text style={styles.zeroStateText}>
              Your threads are set. Scores stay at zero until logged activity starts feeding them —
              that lands with the Nutrition module in Phase 1.
            </Text>
          </View>
        )}

        <Text style={styles.sectionTitle}>Threads</Text>
        {threadScores.map((thread) => (
          <ThreadCard key={thread.threadId} thread={thread} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  content: { padding: 24, paddingBottom: 48 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 },
  greeting: { color: colors.text, fontSize: 24, fontWeight: "800" },
  subGreeting: { color: colors.textMuted, fontSize: 14, marginTop: 4 },
  signOut: { color: colors.accent, fontSize: 13, fontWeight: "600", marginTop: 6 },
  error: { color: colors.bad, marginTop: 12, fontSize: 13 },
  ringWrap: { alignItems: "center", marginVertical: 28 },
  zeroStateNote: {
    backgroundColor: colors.accentSoft,
    borderRadius: 14,
    padding: 14,
    marginBottom: 24,
  },
  zeroStateText: { color: colors.text, fontSize: 13, lineHeight: 19 },
  sectionTitle: { color: colors.textMuted, fontSize: 13, fontWeight: "700", letterSpacing: 1, marginBottom: 12 },
});
