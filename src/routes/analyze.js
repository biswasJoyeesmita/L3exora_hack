const express = require("express");

const {
    analyzeContent,
    ValidationError
} = require("../analyze");

const router = express.Router();

router.post("/analyze", async (req, res, next) => {

    try {

        const { text } = req.body || {};

        const result =
            await analyzeContent(text);

        res.json(result);

    } catch (err) {

        if (err instanceof ValidationError) {

            return res.status(400).json({
                error: err.message
            });
        }

        next(err);
    }
});

module.exports = router;