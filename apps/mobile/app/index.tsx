import { useEffect, useState } from "react";
import { Redirect } from "expo-router";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { useIdentityAuth } from "../context/AuthContext";
import { api } from "../lib/api";

/** Route gate: gets the user to sign-in, onboarding, or the dashboard. */
export default function Index() {
  const auth = useIdentityAuth();
  const [checking, setChecking] = useState(true);
  const [hasThreads, setHasThreads] = useState(false);

  useEffect(() => {
    if (!auth.isLoaded) return;
    if (!auth.isSignedIn) {
      setChecking(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const headers = await auth.authHeaders();
        const dashboard = await api.getDashboard(headers);
        if (!cancelled) setHasThreads(dashboard.threads.length > 0);
      } catch {
        if (!cancelled) setHasThreads(false);
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [auth.isLoaded, auth.isSignedIn]);

  if (!auth.isLoaded || checking) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#6D5DF6" />
      </View>
    );
  }

  if (!auth.isSignedIn) return <Redirect href="/sign-in" />;
  if (!hasThreads) return <Redirect href="/onboarding" />;
  return <Redirect href="/dashboard" />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#0B0B12" },
});
