/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0e1014",
        surface: "#161a20",
        surface2: "#1d222a",
        line: "#2c333d",
        ink: "#f2f4f7",
        muted: "#a9b3c1",
        ok: { bg: "#12301f", fg: "#86efac" },
        warn: { bg: "#3a2b0a", fg: "#fcd34d" },
        bad: { bg: "#3b1517", fg: "#fca5a5" },
        info: { bg: "#14263f", fg: "#93c5fd" },
      },
      fontFamily: {
        sans: ['"Source Sans 3 Variable"', "system-ui", "sans-serif"],
        display: ['"Archivo Variable"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
