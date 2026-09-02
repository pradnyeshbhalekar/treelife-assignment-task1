/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        bg: "#16171d",
        surface: "#1f2028",
        border: "#2e303a",
        muted: "#9ca3af",
        heading: "#f3f4f6",
        accent: "#c084fc",
      },
    },
  },
  plugins: [],
}

