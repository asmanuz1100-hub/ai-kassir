# AI Kassir — Telegram test bot

**This is a NEW, independent project. Do not reuse the existing Hisobchi AI token, Render service, repository or database.**

Cashier sends text or Uzbek/Russian voice; the bot extracts one cash operation, shows the amount, currency, category and counterpart, and writes the transaction to a dedicated PostgreSQL ledger **only after cashier confirmation**. Includes /balance, /today, /month and admin-controlled /allow.

## Deploy on Render

1. Use this repo's `render.yaml` in **Render → New → Blueprint**.
2. Provision a **new** service and **new** database. The test configuration requests free instances; review Render's current limits and availability before approving.
3. In the Blueprint environment prompts, provide `BOT_TOKEN` for a **new bot created with @BotFather**, `ADMIN_TELEGRAM_ID` (your numeric Telegram ID), and `OPENAI_API_KEY` for voice parsing. Never commit or paste tokens into the repository or chat.
4. Render generates `WEBHOOK_SECRET` and connects `DATABASE_URL` from the new database. After the new service is healthy, register the Telegram webhook to `https://<NEW_SERVICE>.onrender.com/webhook/<WEBHOOK_SECRET>` using the Telegram Bot API for the **new** token. Keep the token and secret out of screenshots and browser history.
5. Verify /health and test /start, a 500 USD income, a 1,000,000 UZS salary-advance expense, /balance and /today.

## Safety and MVP limitations

- **Testing only. Do not use for real cash accounting yet.** The balance starts at zero and is only the sum of recorded operations, **not the physical cash balance**; there is no opening balance or cash-day closing.
- One operation per message. AI transcription may be mistaken: **check the amount, currency, category and direction before confirming**.
- Voice parsing requires an OpenAI API key; text supports a conservative fallback without it.
- All authorized cashiers can currently see the shared company ledger. Use trusted staff only.
- No reversal/edit audit trail, multiple cashboxes, real payroll ledger, multi-operation messages, PDF, currency exchange or backups yet.
- Free Render web services may sleep; free databases can have expiration and retention limits. Use durable storage, recovery tests and strict access controls before production.
- Never put secrets, bank statements, customer financial data or private audio into a **public** repository. Make this repository **Private** in GitHub Settings → General → Danger Zone → Change repository visibility.
