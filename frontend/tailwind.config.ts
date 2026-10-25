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
      fontFamily: {
        sans: ["Manrope", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "Courier New", "monospace"],
      },
      colors: {
        /* Surfaces — Midnight Graphite */
        "bg-main":          "#171C21",
        "bg-sidebar":       "#1D242A",
        "bg-panel":         "#252E35",
        "bg-raised":        "#303B43",
        "bg-inset":         "#1A2026",
        "surface-selected": "#223A32",

        /* Borders */
        "border-default": "#3B484F",
        "border-dim":     "#2C363D",

        /* Text */
        "text-pri": "#F2F5F3",
        "text-sec": "#BAC6C3",
        "text-mut": "#98A7A3",

        /* Accent — Jade */
        "accent":         "#62DDB0",
        "accent-hover":   "#7BE7BE",
        "accent-dim":     "#4BBF94",
        "accent-bg":      "#223A32",
        "text-on-accent": "#0F1915",

        /* Semantic — distinct from Jade */
        "success":     "#48BB78",
        "success-bg":  "#1A2F23",
        "warning-c":   "#E0A96D",
        "warning-bg":  "#352818",
        "danger-c":    "#E56B6F",
        "danger-bg":   "#361D20",
      },
      animation: {
        "fade-in":      "fadeIn 0.2s ease-out forwards",
        "slide-in":     "slideIn 0.2s ease-out forwards",
        "pulse-subtle": "pulseSubtle 2s ease-in-out infinite",
        "spin-slow":    "spin 3s linear infinite",
      },
      keyframes: {
        fadeIn:      { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        slideIn:     { from: { opacity: "0", transform: "translateX(8px)" }, to: { opacity: "1", transform: "translateX(0)" } },
        pulseSubtle: { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.6" } },
      },
      borderRadius: {
        "tce": "8px",
      },
    },
  },
  plugins: [],
};
export default config;
