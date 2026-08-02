import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#09090b",
        surface: "#111113",
        card: "#18181b",
        border: "#27272a",
        accent: {
          DEFAULT: "#6366f1",
          hover: "#818cf8",
          muted: "#6366f120",
        },
        success: "#22c55e",
        warning: "#f59e0b",
        error: "#ef4444",
        muted: "#71717a",
        subtle: "#3f3f46",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.5s ease-in-out",
        "slide-up": "slideUp 0.4s ease-out",
        "glow": "glow 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(10px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        glow: { "0%, 100%": { boxShadow: "0 0 5px #6366f140" }, "50%": { boxShadow: "0 0 20px #6366f180" } },
      },
    },
  },
  plugins: [],
};
export default config;
