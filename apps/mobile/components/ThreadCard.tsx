import { StyleSheet, Text, View } from "react-native";
import type { ThreadScore } from "@identity/shared";
import { colors } from "../lib/theme";

export function ThreadCard({ thread }: { thread: ThreadScore }) {
  const trendColor = thread.trend > 0 ? colors.good : thread.trend < 0 ? colors.bad : colors.textMuted;
  const trendLabel = thread.trend === 0 ? "flat" : `${thread.trend > 0 ? "+" : ""}${thread.trend}`;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.label} numberOfLines={2}>
          {thread.label}
        </Text>
        <Text style={[styles.trend, { color: trendColor }]}>{trendLabel}</Text>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${Math.max(0, Math.min(100, thread.score))}%` }]} />
      </View>
      <Text style={styles.score}>
        {Math.round(thread.score)}
        <Text style={styles.scoreMax}>/100</Text>
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  label: { color: colors.text, fontSize: 15, fontWeight: "700", flex: 1, marginRight: 8 },
  trend: { fontSize: 13, fontWeight: "700" },
  barTrack: { height: 8, borderRadius: 4, backgroundColor: colors.surfaceRaised, overflow: "hidden" },
  barFill: { height: 8, borderRadius: 4, backgroundColor: colors.accent },
  score: { color: colors.text, fontSize: 20, fontWeight: "800", marginTop: 10 },
  scoreMax: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
});
