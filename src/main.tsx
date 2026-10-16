import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import SetupGate from "./SetupGate";
import "./style.css";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SetupGate>
      <App />
    </SetupGate>
  </React.StrictMode>,
);
