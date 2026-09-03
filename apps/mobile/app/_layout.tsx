import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { IdentityAuthProvider } from "../context/AuthContext";

export default function RootLayout() {
  return (
    <IdentityAuthProvider>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        <Stack screenOptions={{ headerShown: false }} />
      </SafeAreaProvider>
    </IdentityAuthProvider>
  );
}
