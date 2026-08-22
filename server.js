/* ==========================================================================
   LEXORA — Backend server
   ========================================================================== */

require("dotenv").config();

const { spawn } = require("child_process");
const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");
const rateLimit = require("express-rate-limit");

const analyzeRoute = require("./src/routes/analyze");
const contactRoute = require("./src/routes/contact");
const reportRoute = require("./src/routes/report");

const app = express();
const PORT = process.env.PORT || 3000;
const ORIGIN = process.env.CORS_ORIGIN || "*";
let pythonService;

async function ensurePythonService() {
  if (process.env.START_LEXORA_PYTHON === "false") return;

  try {
    const health = await fetch("http://127.0.0.1:5000/api/health");
    if (health.ok) return;
  } catch { }

  pythonService = spawn(
    process.env.PYTHON_COMMAND || "python",
    ["api_server.py"],
    {
      cwd: `${__dirname}/Lexora`,
      stdio: "inherit",
      windowsHide: true,
    }
  );

  pythonService.on("error", (error) => {
    console.error(`Could not start Lexora Python service: ${error.message}`);
  });
  pythonService.on("exit", (code) => {
    if (code !== 0) {
      console.error(`Lexora Python service exited with code ${code}.`);
    }
  });
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
app.use("/api", reportRoute);

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
app.use("/api", reportRoute);
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
