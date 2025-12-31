import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        black: "#000000",
        slate: {
          950: "#0C0E11",
          900: "#13161A",
          800: "#1A1E24",
          700: "#22272E",
          600: "#2A3038",
          500: "#323A44",
          400: "#3B4450",
          300: "#444F5D",
          200: "#5A677A",
          100: "#707D90",
          50: "#8694A8",
        },
        green: {
          500: "#48f1a6",
          400: "#2bdc98",
          300: "#1f8f67"
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
