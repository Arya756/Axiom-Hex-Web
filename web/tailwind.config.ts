import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class", // Explicitly disabled from auto-switching with OS media
  theme: {
    extend: {
      colors: {
        pastel: {
          bg: "#F8FAFC",
          card: "#FFFFFF",
          border: "#E2E8F0",
          hover: "#F1F5F9",
          muted: "#64748B",
          text: "#0F172A",
          subtext: "#334155",
          // Soft Pastels with WCAG AA compliant text pairs
          green: {
            bg: "#ECFDF5",
            border: "#A7F3D0",
            badge: "#D1FAE5",
            text: "#065F46",
          },
          rose: {
            bg: "#FFF1F2",
            border: "#FECDD3",
            badge: "#FFE4E6",
            text: "#9F1239",
          },
          blue: {
            bg: "#F0F9FF",
            border: "#BAE6FD",
            badge: "#E0F2FE",
            text: "#0369A1",
          },
          amber: {
            bg: "#FFFBEB",
            border: "#FDE68A",
            badge: "#FEF3C7",
            text: "#92400E",
          },
          purple: {
            bg: "#FAF5FF",
            border: "#E9D5FF",
            badge: "#F3E8FF",
            text: "#6B21A8",
          },
          indigo: {
            bg: "#EEF2FF",
            border: "#C7D2FE",
            badge: "#E0E7FF",
            text: "#3730A3",
          },
        },
      },
      boxShadow: {
        pastel: "0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        "pastel-md": "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)",
        "pastel-lg": "0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.03)",
      },
    },
  },
  plugins: [],
};

export default config;

