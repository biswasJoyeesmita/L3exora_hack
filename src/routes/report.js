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

function addSemanticReasons(report) {
    if (!report) return report;

    const sensitiveTopic = /rape|sexual assault|women safety|woman safety|child safety|murder|crime|abuse|violence|terror|victim|harassment|death|killed|missing|protest|riot|communal|war/i.test(report.query || "");
    if (sensitiveTopic && String(report.riskLevel || "").toLowerCase() === "low") {
        const tierStats = report.tierStats || {};
        report.riskLevel = Number(tierStats.tier3 || 0) > 0 || Number(tierStats.tier4 || 0) > 0 ? "High" : "Moderate";
    }

    if (!Array.isArray(report.flaggedComments)) return report;

    const normalizeComment = (item) => {
        if (!/rule-based screening matched/i.test(item.reason || "")) return item;

        const tier = Number(item.tier || 2);
        let reason;
        if (tier >= 4) {
            reason = "The comment expresses a direct or credible threat of physical harm toward a person or group, creating a threatening sentiment that requires human review.";
        } else if (tier === 3) {
            reason = "The comment uses dehumanizing, hateful, or violence-encouraging language, expressing a harmful and hostile sentiment that requires human review.";
        } else {
            reason = "The comment uses insulting or degrading language toward a person, group, or institution, expressing a hostile and disrespectful sentiment that requires human review.";
        }
        return { ...item, reason };
    };

    report.flaggedComments = report.flaggedComments.map(normalizeComment);
    if (Array.isArray(report.videos)) {
        report.videos = report.videos.map((video) => ({
            ...video,
            comments: Array.isArray(video.comments) ? video.comments.map(normalizeComment) : video.comments,
        }));
    }
    return report;
}

// GET latest model report
// If ?query=<hashtag> is provided, triggers the live Lexora pipeline via the
// Python backend and streams the structured JSON result straight to the client.
// Without a query, falls back to the last saved report file.
router.get("/report", async (req, res, next) => {

    try {
        const query = (req.query.query || "").trim();
        const requestedVideos = Math.min(100, Math.max(1, Number.parseInt(req.query.videos || req.query.target_videos || req.query.comments, 10) || 20));

        if (query) {
            // --- LIVE PIPELINE via Python backend ---
            let pythonRes;
            let lastError;

            for (let attempt = 1; attempt <= 5; attempt += 1) {
                try {
                    pythonRes = await fetch("http://127.0.0.1:5000/api/generate_report", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            // Flask enforces the same shared key server-side (see
                            // api_server.py's require_api_key) so the pipeline
                            // can't be triggered directly on port 5000 either,
                            // in case that port is ever reachable on its own.
                            "X-Internal-Key": process.env.LEXORA_API_KEY || ""
                        },
                        body: JSON.stringify({ query, target_videos: requestedVideos })
                    });

                    if (pythonRes.ok) {
                        break;
                    }

                    lastError = new Error(`Python backend returned status ${pythonRes.status}`);
                    if (pythonRes.status >= 400 && pythonRes.status < 500) {
                        break;
                    }
                } catch (error) {
                    lastError = error;
                }

                if (attempt < 5) {
                    await new Promise((resolve) => setTimeout(resolve, 1000 * attempt));
                }
            }

            if (!pythonRes || !pythonRes.ok) {
                if (pythonRes) {
                    let errMsg = "Python backend error.";
                    try { 
                        const errData = await pythonRes.json();
                        errMsg = errData.error || errMsg; 
                    } catch { }
                    return res.status(pythonRes.status).json({ error: errMsg });
                }

                return res.status(503).json({
                    error: "The Lexora Python sentiment model service is currently initializing or loading models into memory. Please wait a few moments and click Analyze again."
                });
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
            return res.json(addSemanticReasons(cached));
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