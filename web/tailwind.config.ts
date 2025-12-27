import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07090d",
          900: "#0b0e13",
          800: "#111827",
          700: "#1b2332",
          600: "#263145"
        },
        neon: {
          500: "#48f1a6",
          400: "#2dd4bf",
          300: "#38bdf8"
        },
        ember: {
          500: "#f59e0b",
          400: "#f97316"
        }
      },
      fontFamily: {
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular"]
      },
      boxShadow: {
        glow: "0 0 40px rgba(72, 241, 166, 0.15)",
        soft: "0 20px 60px rgba(7, 9, 13, 0.6)"
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" }
        }
      },
      animation: {
        float: "float 8s ease-in-out infinite"
      }
    }
  },
  plugins: []
} satisfies Config;
