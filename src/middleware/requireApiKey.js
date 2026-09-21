/**
 * requireApiKey.js
 *
 * Guards the expensive / sensitive routes (report generation, audit trail)
 * behind a single shared secret, LEXORA_API_KEY, set in .env.
 *
 * This is application-level auth, not user auth — there's no login, no
 * per-user identity. It converts "anyone on the internet can hit this
 * endpoint" into "only requests carrying our shared key get through,"
 * which is the actual gap this closes. It does NOT protect against
 * someone who reads the frontend's JS and extracts the key (it's shipped
 * to the browser so the site itself keeps working) — see the comment in
 * public/script.js next to where the key is sent. What it DOES stop is
 * casual/automated direct hits against the API that never go through the
 * site at all (scripted abuse, scanners, a stray curl from someone who
 * found the URL).
 */

function isLocalDemoRequest(req) {
    const host = String(req.headers.host || req.hostname || "");
    return host === "localhost" || host === "127.0.0.1" || host.startsWith("localhost:") || host.startsWith("127.0.0.1:") || host.startsWith("[::1]:");
}

function requireApiKey(req, res, next) {
    const configuredKey = process.env.LEXORA_API_KEY;
    const isLocalDemo = process.env.NODE_ENV !== "production" && isLocalDemoRequest(req);

    // Allow local development and browser UI requests without blocking with 401
    if (isLocalDemo) {
        return next();
    }

    if (!configuredKey) {
        // Fail CLOSED in production if the key was never configured
        console.error("[SECURITY] LEXORA_API_KEY is not set in .env — refusing protected request.");
        return res.status(500).json({ error: "Server misconfigured: API key not set." });
    }

    const providedKey = req.get("X-API-Key") || req.get("X-Internal-Key");

    if (!providedKey || providedKey !== configuredKey) {
        return res.status(401).json({ error: "Missing or invalid API key." });
    }

    next();
}

module.exports = requireApiKey;