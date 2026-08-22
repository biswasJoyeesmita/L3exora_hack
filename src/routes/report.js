const express = require("express");
const fs = require("fs");
const path = require("path");

const {
    parseReport
} = require("../reportParser");

const router = express.Router();

const REPORT_PATH = path.join(
    process.cwd(),
    "model-output",
    "youtube_feed_report.txt"
);

// GET latest model report
// If ?query=<hashtag> is provided, triggers the live Lexora pipeline via the
// Python backend and streams the structured JSON result straight to the client.
// Without a query, falls back to the last saved report file.
router.get("/report", async (req, res, next) => {

    try {
        const query = (req.query.query || "").trim();
        const requestedComments = Math.min(200, Math.max(1, Number.parseInt(req.query.comments, 10) || 200));

        if (query) {
            // --- LIVE PIPELINE via Python backend ---
            let pythonRes;
            try {
                pythonRes = await fetch("http://127.0.0.1:5000/api/generate_report", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ query, target_comments: requestedComments })
                });
            } catch (error) {
                return res.status(503).json({
                    error: "The Lexora Python model service is unavailable. Start it with: python Lexora/api_server.py"
                });
            }

            if (!pythonRes.ok) {
                let errMsg = "Python backend error.";
                try { errMsg = (await pythonRes.json()).error || errMsg; } catch { }
                return res.status(pythonRes.status).json({ error: errMsg });
            }

            // Python already returns structured JSON — forward it directly.
            const report = await pythonRes.json();

            // Cache a text copy for the "load last report" button (no query)
            try {
                const summaryText = `QUERY: ${report.query}\nSCANNED: ${report.commentsScanned}\nFLAGGED: ${report.flagged}\n`;
                fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
                fs.writeFileSync(REPORT_PATH + ".json", JSON.stringify(report), "utf8");
            } catch { }

            return res.json(report);
        }

        // --- FALLBACK: load cached JSON from last run ---
        const jsonPath = REPORT_PATH + ".json";
        if (fs.existsSync(jsonPath)) {
            const cached = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
            return res.json(cached);
        }

        // Last resort: parse the old-style txt file if it exists
        if (!fs.existsSync(REPORT_PATH)) {
            return res.status(404).json({
                error: "No report found. Enter a hashtag and click Load to generate one.",
                expectedFile: "model-output/youtube_feed_report.txt"
            });
        }

        const text = fs.readFileSync(REPORT_PATH, "utf8");
        const report = parseReport(text);
        res.json(report);

    } catch (error) {
        next(error);
    }
});



// POST report directly from your model
router.post("/report", express.text({
    type: [
        "text/plain",
        "text/*"
    ],
    limit: "5mb"
}), (req, res, next) => {

    try {

        const text = req.body;

        if (
            typeof text !== "string" ||
            !text.trim()
        ) {

            return res.status(400).json({
                error:
                    "Model report body is empty."
            });
        }

        const report =
            parseReport(text);

        res.json(report);

    } catch (error) {

        next(error);
    }
});

module.exports = router;