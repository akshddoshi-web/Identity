import { calculateAutoCalorieTarget, formatCents } from "@identity/shared";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { clearToken, getToken, login, signup, trpcCall } from "./lib/api";

type Screen = "login" | "signup" | "dashboard";

export default function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    getToken().then((token) => {
      if (token) setScreen("dashboard");
      setCheckingSession(false);
    });
  }, []);

  if (checkingSession) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color="#22b587" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      {screen === "login" && <LoginScreen onLoggedIn={() => setScreen("dashboard")} onSignupPress={() => setScreen("signup")} />}
      {screen === "signup" && <SignupScreen onSignedUp={() => setScreen("dashboard")} onLoginPress={() => setScreen("login")} />}
      {screen === "dashboard" && <DashboardScreen onSignOut={() => setScreen("login")} />}
    </SafeAreaView>
  );
}

function LoginScreen({ onLoggedIn, onSignupPress }: { onLoggedIn: () => void; onSignupPress: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.form}>
      <Text style={styles.title}>Identity</Text>
      <Text style={styles.subtitle}>Sign in</Text>
      <TextInput style={styles.input} placeholder="Email" placeholderTextColor="#7c8f8c" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={styles.input} placeholder="Password" placeholderTextColor="#7c8f8c" secureTextEntry value={password} onChangeText={setPassword} />
      {error && <Text style={styles.error}>{error}</Text>}
      <TouchableOpacity style={styles.button} onPress={handleLogin} disabled={loading}>
        <Text style={styles.buttonText}>{loading ? "Signing in..." : "Sign in"}</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={onSignupPress}>
        <Text style={styles.link}>Need an account? Sign up</Text>
      </TouchableOpacity>
    </View>
  );
}

function SignupScreen({ onSignedUp, onLoginPress }: { onSignedUp: () => void; onLoginPress: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSignup() {
    setLoading(true);
    setError(null);
    try {
      await signup(email, password, name || undefined);
      onSignedUp();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.form}>
      <Text style={styles.title}>Identity</Text>
      <Text style={styles.subtitle}>Create your account</Text>
      <TextInput style={styles.input} placeholder="Name" placeholderTextColor="#7c8f8c" value={name} onChangeText={setName} />
      <TextInput style={styles.input} placeholder="Email" placeholderTextColor="#7c8f8c" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={styles.input} placeholder="Password (min 8 chars)" placeholderTextColor="#7c8f8c" secureTextEntry value={password} onChangeText={setPassword} />
      {error && <Text style={styles.error}>{error}</Text>}
      <TouchableOpacity style={styles.button} onPress={handleSignup} disabled={loading}>
        <Text style={styles.buttonText}>{loading ? "Creating..." : "Create account"}</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={onLoginPress}>
        <Text style={styles.link}>Already have an account? Sign in</Text>
      </TouchableOpacity>
    </View>
  );
}

interface NetWorth {
  netWorthCents: number;
  assetsCents: number;
  liabilitiesCents: number;
}

function DashboardScreen({ onSignOut }: { onSignOut: () => void }) {
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    trpcCall<NetWorth>("finance.netWorth", undefined)
      .then(setNetWorth)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  // Demonstrates @identity/shared's business logic running natively, with
  // zero network round-trip — the same BMR/TDEE math the web app uses.
  const sampleTarget = calculateAutoCalorieTarget({
    sex: "male",
    weightKg: 80,
    heightCm: 180,
    age: 30,
    activityLevel: "moderately_active",
    goal: "maintain",
  });

  return (
    <ScrollView contentContainerStyle={styles.form}>
      <Text style={styles.title}>Overview</Text>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Net worth</Text>
        {loadError && <Text style={styles.error}>{loadError}</Text>}
        {!loadError && (
          <Text style={styles.cardValue}>{netWorth ? formatCents(netWorth.netWorthCents) : "Loading..."}</Text>
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardLabel}>Shared calorie math (packages/shared, no network)</Text>
        <Text style={styles.cardValue}>{sampleTarget.calorieTarget} kcal/day target</Text>
        <Text style={styles.cardSub}>
          BMR {sampleTarget.bmr} &middot; TDEE {sampleTarget.tdee}
        </Text>
      </View>

      <TouchableOpacity
        style={styles.button}
        onPress={async () => {
          await clearToken();
          onSignOut();
        }}
      >
        <Text style={styles.buttonText}>Sign out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0b0f10" },
  form: { flexGrow: 1, justifyContent: "center", padding: 24, gap: 12 },
  title: { fontSize: 28, fontWeight: "600", color: "#f5f8f6" },
  subtitle: { fontSize: 16, color: "#a9b8b4", marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: "#26302f",
    backgroundColor: "#1a2224",
    borderRadius: 10,
    padding: 12,
    color: "#e8efec",
  },
  button: { backgroundColor: "#14966f", borderRadius: 10, padding: 14, alignItems: "center", marginTop: 8 },
  buttonText: { color: "#0b0f10", fontWeight: "600" },
  link: { color: "#22b587", textAlign: "center", marginTop: 8 },
  error: { color: "#e2600f" },
  card: { backgroundColor: "#1a2224", borderRadius: 12, padding: 16, borderWidth: 1, borderColor: "#26302f" },
  cardLabel: { color: "#7c8f8c", fontSize: 12, textTransform: "uppercase", marginBottom: 4 },
  cardValue: { color: "#f5f8f6", fontSize: 22, fontWeight: "600" },
  cardSub: { color: "#a9b8b4", fontSize: 12, marginTop: 4 },
});
