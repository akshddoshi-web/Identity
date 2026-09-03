import Svg, { Circle } from "react-native-svg";
import { StyleSheet, Text, View } from "react-native";
import { colors } from "../lib/theme";

const SIZE = 200;
const STROKE = 14;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function IdentityScoreRing({ score, isZeroState }: { score: number; isZeroState: boolean }) {
  const progress = Math.max(0, Math.min(100, score)) / 100;
  const dashOffset = CIRCUMFERENCE * (1 - progress);

  return (
    <View style={styles.wrap}>
      <Svg width={SIZE} height={SIZE}>
        <Circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} stroke={colors.border} strokeWidth={STROKE} fill="none" />
        <Circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          stroke={colors.accent}
          strokeWidth={STROKE}
          fill="none"
          strokeDasharray={`${CIRCUMFERENCE} ${CIRCUMFERENCE}`}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          rotation={-90}
          originX={SIZE / 2}
          originY={SIZE / 2}
        />
      </Svg>
      <View style={styles.center}>
        <Text style={styles.score}>{Math.round(score)}</Text>
        <Text style={styles.label}>{isZeroState ? "Getting started" : "Identity Score"}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { width: SIZE, height: SIZE, alignItems: "center", justifyContent: "center" },
  center: { position: "absolute", alignItems: "center" },
  score: { fontSize: 56, fontWeight: "800", color: colors.text },
  label: { fontSize: 13, color: colors.textMuted, marginTop: 4 },
});
