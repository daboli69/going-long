/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { bg: "#0b1220", panel: "#111b2e", panel2: "#0f1a2e", line: "#1e2b45", muted: "#9fb0cc", accent: "#34d399", warn: "#fbbf24", bad: "#f87171", info: "#60a5fa" },
      fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
