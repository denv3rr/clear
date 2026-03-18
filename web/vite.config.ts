import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return;
          }
          if (
            id.includes("plotly.js-dist-min") ||
            id.includes("react-plotly.js")
          ) {
            return "plotly";
          }
          if (
            id.includes("@react-three/") ||
            id.includes("\\three\\") ||
            id.includes("/three/") ||
            id.includes("postprocessing")
          ) {
            return "globe";
          }
          if (id.includes("maplibre-gl")) {
            return "maplibre";
          }
          if (id.includes("leaflet")) {
            return "leaflet";
          }
          if (id.includes("recharts")) {
            return "charts";
          }
          if (
            id.includes("react-markdown") ||
            id.includes("remark-gfm") ||
            id.includes("/remark-") ||
            id.includes("\\remark-") ||
            id.includes("/mdast-") ||
            id.includes("\\mdast-") ||
            id.includes("/hast-") ||
            id.includes("\\hast-") ||
            id.includes("/micromark") ||
            id.includes("\\micromark") ||
            id.includes("/unist-") ||
            id.includes("\\unist-")
          ) {
            return "markdown";
          }
          if (
            id.includes("react-router") ||
            id.includes("\\react\\") ||
            id.includes("/react/") ||
            id.includes("scheduler")
          ) {
            return "react-vendor";
          }
          return "vendor";
        }
      }
    }
  },
  server: {
    port: 5173
  }
});
