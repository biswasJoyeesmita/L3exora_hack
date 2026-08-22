const express = require("express");

const router = express.Router();

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// In-memory store so the demo works out of the box.
// FUTURE: replace with a real persistence layer (DB) and/or an email
// service (SendGrid, Postmark, SES, etc.) to actually deliver the message.
const submissions = [];

/**
 * POST /api/contact
 * body: { name, email, message }
 */
router.post("/contact", (req, res) => {
  const { name, email, message } = req.body ?? {};

  const errors = {};
  if (!name || !String(name).trim()) errors.name = "Name is required.";
  if (!email || !EMAIL_RE.test(String(email).trim())) errors.email = "A valid email is required.";
  if (!message || !String(message).trim()) errors.message = "Message is required.";

  if (Object.keys(errors).length > 0) {
    return res.status(400).json({ error: "Validation failed.", fields: errors });
  }

  const submission = {
    id: submissions.length + 1,
    name: String(name).trim(),
    email: String(email).trim(),
    message: String(message).trim(),
    receivedAt: new Date().toISOString(),
  };

  submissions.push(submission);

  res.status(201).json({ success: true, id: submission.id });
});

module.exports = router;
