function cleanValue(value) {
    return String(value || "")
        .replace(/\r/g, "")
        .trim();
}

function parseNumber(value) {
    const n = Number(String(value || "").replace(/[^\d]/g, ""));
    return Number.isFinite(n) ? n : 0;
}

function tierLabel(tier) {
    if (tier === 2) return "Abusive / Disrespectful";
    if (tier === 3) return "Hate Speech / Incitement";
    if (tier === 4) return "Direct Threat";
    return "Lawful / Neutral";
}

function parseReport(text) {

    if (typeof text !== "string" || !text.trim()) {
        throw new Error("Model report is empty.");
    }

    const lines = text
        .replace(/\r/g, "")
        .split("\n");

    const report = {
        source: "YouTube Data API",
        reportType: "social-media-monitoring",
        query: "",
        commentsScanned: 0,
        flagged: 0,
        lawful: 0,

        tierStats: {
            tier1: 0,
            tier2: 0,
            tier3: 0,
            tier4: 0
        },

        riskLevel: "Unknown",

        humanReviewOnly: true,

        videos: [],

        socialImpactAssessment: "",
        topicSummary: "",

        generatedAt: new Date().toISOString()
    };

    let currentVideo = null;
    let currentComment = null;

    function finishComment() {

        if (!currentComment) return;

        if (currentVideo) {
            currentVideo.comments.push(currentComment);
        }

        currentComment = null;
    }

    function finishVideo() {

        finishComment();

        if (currentVideo) {
            report.videos.push(currentVideo);
        }

        currentVideo = null;
    }

    for (let i = 0; i < lines.length; i++) {

        const raw = lines[i];
        const line = raw.trim();

        if (!line) continue;

        // Query
        if (/Query\s*\/\s*Hashtag\s*:/i.test(line)) {

            report.query =
                cleanValue(
                    line.split(":").slice(1).join(":")
                );

            continue;
        }

        // Summary
        const summaryMatch = line.match(
            /Comments\s+Scanned\s*:\s*(\d+)\s*\|\s*Flagged\s*:\s*(\d+)\s*\|\s*Lawful\s*:\s*(\d+)/i
        );

        if (summaryMatch) {

            report.commentsScanned =
                parseNumber(summaryMatch[1]);

            report.flagged =
                parseNumber(summaryMatch[2]);

            report.lawful =
                parseNumber(summaryMatch[3]);

            continue;
        }

        // Human review
        if (/human review only/i.test(line)) {
            report.humanReviewOnly = true;
            continue;
        }

        // Video
        const videoMatch = line.match(
            /^\[(\d+)\]\s+(.+)$/
        );

        if (
            videoMatch &&
            !/TIER/i.test(videoMatch[2])
        ) {

            finishVideo();

            currentVideo = {
                index:
                    parseNumber(videoMatch[1]),

                title:
                    cleanValue(videoMatch[2]),

                url: "",

                flaggedComments: 0,

                comments: []
            };

            continue;
        }

        // URL
        if (
            currentVideo &&
            /^URL\s*:/i.test(line)
        ) {

            currentVideo.url =
                cleanValue(
                    line.substring(
                        line.indexOf(":") + 1
                    )
                );

            continue;
        }

        // Number of flagged comments for video
        if (
            currentVideo &&
            /Flagged comments on this video/i.test(line)
        ) {

            const match =
                line.match(/:\s*(\d+)/);

            currentVideo.flaggedComments =
                match
                    ? parseNumber(match[1])
                    : 0;

            continue;
        }

        // Tier
        const tierMatch = line.match(
            /^TIER\s+([234])\s+\((.+)\)$/i
        );

        if (tierMatch) {

            finishComment();

            const tier =
                parseNumber(tierMatch[1]);

            currentComment = {

                tier,

                tierLabel:
                    tierLabel(tier),

                user: "",

                comment: "",

                reason: ""
            };

            continue;
        }

        // User
        if (
            currentComment &&
            /^User\s*:/i.test(line)
        ) {

            currentComment.user =
                cleanValue(
                    line.substring(
                        line.indexOf(":") + 1
                    )
                );

            continue;
        }

        // Comment
        if (
            currentComment &&
            /^Comment\s*:/i.test(line)
        ) {

            let value =
                line.substring(
                    line.indexOf(":") + 1
                ).trim();

            // Remove opening quote
            if (value.startsWith('"')) {
                value = value.substring(1);
            }

            // Same-line closing quote
            if (
                value.endsWith('"') &&
                value.length > 1
            ) {

                value =
                    value.substring(
                        0,
                        value.length - 1
                    );
            }

            currentComment.comment =
                value;

            // Collect multiline comment
            for (
                let j = i + 1;
                j < lines.length;
                j++
            ) {

                const next =
                    lines[j].trim();

                if (
                    /^Reason\s*:/i.test(next)
                ) {

                    i = j - 1;
                    break;
                }

                if (
                    /^TIER\s+[234]/i.test(next) ||
                    /^={3,}/.test(next) ||
                    /^-{3,}/.test(next) ||
                    /^\[\d+\]\s+/.test(next)
                ) {

                    i = j - 1;
                    break;
                }

                if (next) {

                    currentComment.comment +=
                        "\n" + next;
                }

                i = j;
            }

            currentComment.comment =
                currentComment.comment
                    .replace(/^"+|"+$/g, "")
                    .trim();

            continue;
        }

        // Reason
        if (
            currentComment &&
            /^Reason\s*:/i.test(line)
        ) {

            currentComment.reason =
                cleanValue(
                    line.substring(
                        line.indexOf(":") + 1
                    )
                );

            continue;
        }

        // Overall tier statistics
        const tier1Match =
            line.match(
                /Tier\s*1\s+Lawful\s*\/\s*Neutral\s*:\s*(\d+)/i
            );

        if (tier1Match) {

            report.tierStats.tier1 =
                parseNumber(tier1Match[1]);

            continue;
        }

        const tier2Match =
            line.match(
                /Tier\s*2\s+Abusive\s*:\s*(\d+)/i
            );

        if (tier2Match) {

            report.tierStats.tier2 =
                parseNumber(tier2Match[1]);

            continue;
        }

        const tier3Match =
            line.match(
                /Tier\s*3\s+Hate Speech\s*:\s*(\d+)/i
            );

        if (tier3Match) {

            report.tierStats.tier3 =
                parseNumber(tier3Match[1]);

            continue;
        }

        const tier4Match =
            line.match(
                /Tier\s*4\s+Direct Threat\s*:\s*(\d+)/i
            );

        if (tier4Match) {

            report.tierStats.tier4 =
                parseNumber(tier4Match[1]);

            continue;
        }

        // Risk
        const riskMatch =
            line.match(
                /RISK LEVEL\s*:\s*(.+)$/i
            );

        if (riskMatch) {

            report.riskLevel =
                cleanValue(
                    riskMatch[1]
                );

            continue;
        }

        // Social impact assessment
        if (
            /^Based on \d+ YouTube comments/i.test(line)
        ) {

            let assessment = line;

            for (
                let j = i + 1;
                j < lines.length;
                j++
            ) {

                const next =
                    lines[j].trim();

                if (
                    /^={3,}/.test(next)
                ) {
                    i = j;
                    break;
                }

                if (next) {
                    assessment += " " + next;
                }

                i = j;
            }

            report.socialImpactAssessment =
                assessment.trim();
        }
    }

    finishVideo();

    // Fallback statistics if report supplied only summary
    if (
        report.tierStats.tier1 === 0 &&
        report.lawful > 0
    ) {
        report.tierStats.tier1 =
            report.lawful;
    }

    if (
        report.tierStats.tier2 === 0 &&
        report.tierStats.tier3 === 0 &&
        report.tierStats.tier4 === 0
    ) {

        const flaggedComments =
            report.videos.flatMap(
                v => v.comments
            );

        for (const comment of flaggedComments) {

            if (comment.tier === 2)
                report.tierStats.tier2++;

            if (comment.tier === 3)
                report.tierStats.tier3++;

            if (comment.tier === 4)
                report.tierStats.tier4++;
        }
    }

    report.totalVideos =
        report.videos.length;

    report.flaggedComments =
        report.videos.flatMap(
            video =>
                video.comments.map(
                    comment => ({
                        ...comment,

                        videoTitle:
                            video.title,

                        videoUrl:
                            video.url
                    })
                )
        );

    return report;
}

module.exports = {
    parseReport
};