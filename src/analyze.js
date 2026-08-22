const { getLexicon } = require("./data/lexicon");

const MAX_INPUT_LENGTH = 10000;

class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = "ValidationError";
        this.statusCode = 400;
    }
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findMatches(text) {

    const lexicon = getLexicon();

    const lowerText = text.toLowerCase();

    const matches = [];

    for (const entry of lexicon) {

        const pattern = new RegExp(
            `\\b${escapeRegex(entry.word.toLowerCase())}\\b`,
            "gi"
        );

        const found = lowerText.match(pattern);

        if (found) {

            matches.push({
                ...entry,
                occurrences: found.length
            });
        }
    }

    return matches;
}
function classifyTier(matches) {

    if (!matches || matches.length === 0) {

        return {
            tier: 1,
            category: "Lawful / Neutral",
            risk: "Low"
        };
    }

    const hasThreat = matches.some(
        m => m.category === "threatening"
    );

    const hasIncitement = matches.some(
        m =>
            m.category === "incitement" ||
            m.category === "hate"
    );

    const hasAbuse = matches.some(
        m =>
            m.category === "abusive" ||
            m.category === "offensive"
    );

    if (hasThreat) {

        return {
            tier: 4,
            category: "Direct Threat",
            risk: "Critical"
        };
    }

    if (hasIncitement) {

        return {
            tier: 3,
            category: "Hate Speech / Incitement",
            risk: "High"
        };
    }

    if (hasAbuse) {

        return {
            tier: 2,
            category: "Abusive / Disrespectful",
            risk: "Moderate"
        };
    }

    return {
        tier: 1,
        category: "Lawful / Neutral",
        risk: "Low"
    };
}
async function analyzeContent(rawText) {

    if (typeof rawText !== "string") {

        throw new ValidationError(
            "`text` must be a string."
        );
    }

    const text = rawText.trim();

    if (!text) {

        throw new ValidationError(
            "`text` must not be empty."
        );
    }

    if (text.length > MAX_INPUT_LENGTH) {

        throw new ValidationError(
            `Text exceeds ${MAX_INPUT_LENGTH} characters.`
        );
    }

    try {
        const response = await fetch("http://127.0.0.1:5000/api/classify-text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            throw new Error(`Python API error: ${response.status}`);
        }

        const data = await response.json();

        return {
            comment: text,
            matches: (data.flagged_terms || []).map(word => ({ word, meaning: data.justification, category: data.tier_label })),
            wordCount: text.split(/\s+/).filter(Boolean).length,
            slangCount: (data.flagged_terms || []).length,
            tier: data.tier || 1,
            category: data.tier_label || "Unknown",
            risk: data.tier >= 3 ? "High" : (data.tier === 2 ? "Moderate" : "Low"),
            humanReview: (data.tier || 1) >= 2,
            reason: data.justification || (data.flagged_terms && data.flagged_terms.length ? "Detected language requiring review." : "No flagged language detected.")
        };
    } catch (err) {
        console.error("Failed to connect to Python backend, falling back to local lexicon:", err.message);

        const matches = findMatches(text);

        const classification =
            classifyTier(matches);

        return {

            comment: text,

            matches: matches.map(
                ({ word, meaning, category }) => ({
                    word,
                    meaning,
                    category
                })
            ),

            wordCount:
                text.split(/\s+/).filter(Boolean).length,

            slangCount:
                matches.length,

            tier:
                classification.tier,

            category:
                classification.category,

            risk:
                classification.risk,

            humanReview:
                classification.tier >= 2,

            reason:
                matches.length
                    ? "Detected language requiring review."
                    : "No flagged language detected."
        };
    }
}

module.exports = {
    analyzeContent,
    ValidationError
};