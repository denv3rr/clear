import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "leaflet/dist/leaflet.css";

const useHashRouter = import.meta.env.VITE_HASH_ROUTER === "true";
const Router = useHashRouter ? HashRouter : BrowserRouter;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Router {...(!useHashRouter ? { basename: import.meta.env.BASE_URL } : {})}>
      <App />
    </Router>
  </React.StrictMode>
);
