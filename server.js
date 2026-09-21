/* ==========================================================================
   LEXORA — Backend server
   ========================================================================== */

require("dotenv").config(); // load .env (LEXORA_API_KEY, GEMINI_API_KEY, etc.) before anything else reads process.env

const fs = require("fs");
const path = require("path");
const { spawn, spawnSync } = require("child_process");
const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");
const rateLimit = require("express-rate-limit");

const analyzeRoute = require("./src/routes/analyze");
const contactRoute = require("./src/routes/contact");
const reportRoute = require("./src/routes/report");
const auditRoute = require("./src/routes/audit");
const requireApiKey = require("./src/middleware/requireApiKey");

const app = express();
const PORT = process.env.PORT || 3000;
const ORIGIN = process.env.CORS_ORIGIN || "*";
let pythonService;

function resolvePythonCommand() {
  if (process.env.PYTHON_COMMAND) {
    return process.env.PYTHON_COMMAND.split(/\s+/).filter(Boolean);
  }

  const preferred = ["python", "python3", "py"];
  for (const candidate of preferred) {
    const result = spawnSync(candidate, ["--version"], { stdio: "ignore" });
    if (result.error === undefined) {
      return [candidate];
    }
  }

  return ["python"];
}

async function ensurePythonService() {
  if (process.env.START_LEXORA_PYTHON === "false") return;

  const startupTimeoutMs = Number(process.env.PYTHON_START_TIMEOUT_MS || 30000);
  const startedAt = Date.now();
  let attempt = 0;

  while (Date.now() - startedAt < startupTimeoutMs) {
    attempt++;
    try {
      const health = await fetch("http://127.0.0.1:5000/api/health");
      if (health.ok) {
        console.log("Lexora Python service is connected and ready.");
        return;
      }
    } catch { }

    // Wait a brief 2s window for an external runner (e.g. concurrently) to initialize Python
    if (attempt >= 3 && !pythonService) {
      const scriptDir = fs.existsSync(path.join(__dirname, "Lexora", "L3exora_hack"))
        ? path.join(__dirname, "Lexora", "L3exora_hack")
        : __dirname;

      const [pythonBinary, ...pythonArgs] = resolvePythonCommand();
      try {
        pythonService = spawn(
          pythonBinary,
          [...pythonArgs, "api_server.py"],
          {
            cwd: scriptDir,
            stdio: "inherit",
            windowsHide: true,
          }
        );

        pythonService.on("error", (error) => {
          console.error(`Could not start Lexora Python service: ${error.message}`);
        });
        pythonService.on("exit", (code) => {
          if (code !== 0 && code !== null) {
            console.error(`Lexora Python service exited with code ${code}.`);
          }
          pythonService = null;
        });
      } catch (err) {
        console.error(`Spawn failed: ${err.message}`);
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 800));
  }

  console.warn("Lexora Python service did not become healthy within the startup timeout.");
}

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'"],
      styleSrc: ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://cdnjs.cloudflare.com"],
      fontSrc: ["'self'", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com", "data:"],
      imgSrc: ["'self'", "data:", "https:"],
      connectSrc: ["'self'"],
      objectSrc: ["'none'"],
    },
  },
}));
app.use(cors({ origin: ORIGIN }));
app.use(express.json({ limit: "100kb" }));
app.use(morgan(process.env.NODE_ENV === "production" ? "combined" : "dev"));
app.use(express.static("public"));

// Rate limiting: generous for /api/analyze (users may test repeatedly),
// stricter for /api/contact (prevent spam/abuse of the form).
const analyzeLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many analysis requests. Please slow down." },
});

const contactLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 5,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many contact submissions. Please try again later." },
});

app.get("/api/health", (req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

app.use("/api", analyzeLimiter, analyzeRoute);
app.use("/api", contactLimiter, contactRoute);
// Report generation and the audit trail are the expensive / sensitive
// surface — gated behind LEXORA_API_KEY. The live-demo classify/analyze
// routes above stay public (rate-limited only), same as before.
app.use("/api", requireApiKey, reportRoute);
app.use("/api", requireApiKey, auditRoute);
app.use(express.static("public"));
// 404 handler
app.use((req, res) => {
  res.status(404).json({
    error: "Not found."
  });
});

// Central error handler
app.use((err, req, res, next) => {
  console.error(err);
  res.status(err.statusCode || 500).json({ error: err.message || "Internal server error." });
});

process.on("exit", () => pythonService?.kill());

app.listen(PORT, () => {
  console.log(`LEXORA backend listening on http://localhost:${PORT}`);
  ensurePythonService().catch((error) => {
    console.error(`Could not initialize Lexora Python service: ${error.message}`);
  });
});

module.exports = app;