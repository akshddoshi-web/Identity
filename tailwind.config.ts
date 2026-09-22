import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        panel: "var(--panel)",
        panel2: "var(--panel2)",
        panel3: "var(--panel3)",
        border: "var(--border)",
        text: "var(--text)",
        sub: "var(--sub)",
        accent: "var(--accent)",
        "accent-dim": "var(--accent-dim)",
        blue: "var(--blue)",
        purple: "var(--purple)",
        orange: "var(--orange)",
        red: "var(--red)",
        yellow: "var(--yellow)",
        pink: "var(--pink)",
        pos: "var(--pos)",
        neg: "var(--neg)",
        warn: "var(--warn)",
      },
      fontFamily: {
        sans: [
          "Space Grotesk",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        sharp: "var(--radius)",
        none: "0px",
      },
      maxWidth: {
        app: "1220px",
        rm: "640px",
      },
    },
  },
  plugins: [],
} satisfies Config;
