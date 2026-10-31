/** @type {import('tailwindcss').Config} */
// Scorebug look: flat charcoal surfaces, team colours as solid fields, one yellow for the active tab, focus and warnings.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#16181b", panel: "#1f2226", panel2: "#0e0f11", line: "#2c3036", muted: "#a9adb3",
        accent: "#ffcf3f", warn: "#ffcf3f", bad: "#f87171", info: "#60a5fa", chart: "#8b9097",
        white: "#f2f2f0", slate: { 100: "#f2f2f0", 300: "#d0d3d7" },
      },
      // Bahnschrift ships with Windows (the only place this local app runs) and gives the broadcast DIN feel.
      fontFamily: { sans: ["Bahnschrift", "DIN Alternate", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
