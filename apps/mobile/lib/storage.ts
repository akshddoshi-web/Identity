import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

/**
 * expo-secure-store has no web implementation and throws there, but the app
 * still needs to run on `expo start --web`. This wraps it with a localStorage
 * fallback on web and the real secure store on native.
 */
export const storage = {
  async getItem(key: string): Promise<string | null> {
    if (Platform.OS === "web") {
      try {
        return typeof localStorage !== "undefined" ? localStorage.getItem(key) : null;
      } catch {
        return null;
      }
    }
    return SecureStore.getItemAsync(key);
  },

  async setItem(key: string, value: string): Promise<void> {
    if (Platform.OS === "web") {
      try {
        localStorage.setItem(key, value);
      } catch {
        // ignore (e.g. private browsing)
      }
      return;
    }
    await SecureStore.setItemAsync(key, value);
  },

  async removeItem(key: string): Promise<void> {
    if (Platform.OS === "web") {
      try {
        localStorage.removeItem(key);
      } catch {
        // ignore
      }
      return;
    }
    await SecureStore.deleteItemAsync(key);
  },
};
