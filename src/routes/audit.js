const express = require("express");
const router = express.Router();

async function waitForPythonAuditService() {
    const maxAttempts = 20;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        try {
            const health = await fetch("http://127.0.0.1:5000/api/health");
            if (health.ok) return;
        } catch (error) {
            // the Python service may still be booting; keep retrying until
            // the audit endpoints are ready to answer requests.
        }

        await new Promise((resolve) => setTimeout(resolve, 500));
    }
}

// Both routes proxy straight to the Flask audit_log endpoints — same
// pattern as src/routes/report.js's live-pipeline proxy, just without the
// caching/retry logic since these are cheap, fast, read-only calls.

router.get("/audit/verify", async (req, res, next) => {
    try {
        await waitForPythonAuditService();
        const pyRes = await fetch("http://127.0.0.1:5000/api/audit/verify", {
            headers: { "X-Internal-Key": process.env.LEXORA_API_KEY || "" }
        });
        let data;
        try {
            data = await pyRes.json();
        } catch (parseError) {
            data = { error: "The audit service responded with invalid JSON." };
        }
        res.status(pyRes.status).json(data);
    } catch (error) {
        res.status(503).json({
            error: "The Lexora Python service is currently unavailable or starting up. Please try again in a few moments."
        });
    }
});

router.get("/audit/log", async (req, res, next) => {
    try {
        await waitForPythonAuditService();
        const limit = req.query.limit ?? "50";
        const offset = req.query.offset ?? "0";
        const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
        const pyRes = await fetch(`http://127.0.0.1:5000/api/audit/log?${params.toString()}`, {
            headers: { "X-Internal-Key": process.env.LEXORA_API_KEY || "" }
        });
        let data;
        try {
            data = await pyRes.json();
        } catch (parseError) {
            data = { error: "The audit service responded with invalid JSON." };
        }
        res.status(pyRes.status).json(data);
    } catch (error) {
        res.status(503).json({
            error: "The Lexora Python service is currently unavailable or starting up. Please try again in a few moments."
        });
    }
});

module.exports = router;