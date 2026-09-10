import type { Config } from "tailwindcss";

/**
 * Design identity: "Ledger & Iron" — a deep ink dashboard base (not
 * default Tailwind gray) with two accent families that map to the app's
 * two domains: teal/jade for finance, ember for fitness/training. Neutrals
 * are a warm ink scale rather than pure gray so dark mode doesn't look
 * like unstyled defaults.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0f10",
          900: "#12181a",
          800: "#1a2224",
          700: "#26302f",
          600: "#374544",
          500: "#526462",
          400: "#7c8f8c",
          300: "#a9b8b4",
          200: "#d2ddd9",
          100: "#e8efec",
          50: "#f5f8f6",
        },
        jade: {
          600: "#0f7a5f",
          500: "#14966f",
          400: "#22b587",
          300: "#63d3ad",
        },
        ember: {
          600: "#c2440c",
          500: "#e2600f",
          400: "#f2842f",
          300: "#f7ab6b",
        },
        gold: {
          500: "#c99a2e",
          400: "#e0b34a",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
