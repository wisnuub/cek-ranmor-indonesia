import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "merah": {
          50:  "#fff1f1",
          100: "#ffe0e0",
          500: "#DC2626",
          600: "#B91C1C",
          700: "#991B1B",
        },
        "abu": {
          50:  "#F9FAFB",
          100: "#F3F4F6",
          200: "#E5E7EB",
          700: "#374151",
          800: "#1F2937",
          900: "#111827",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
