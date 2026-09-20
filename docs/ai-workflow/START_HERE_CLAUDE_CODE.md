# Start Here: Claude Code

1. Create a local `.env` file from `.env.example`.
2. Add API keys only after creating the accounts listed in `docs/ACCOUNT_AND_API_SETUP.md`.
3. Keep `KALSHI_ENABLE_LIVE_TRADING=false` and `TRADING_MODE=paper`.
4. Open this repository in Claude Code.
5. Paste the entire contents of `docs/CLAUDE_CODE_MASTER_PROMPT.md` as your first Claude Code message.
6. Claude Code must first run the test suite and produce a safe configuration audit that reports only `SET` or `MISSING` for expected environment variables.

The project intentionally separates research from execution. Claude Code may research and test model changes in the sandbox, but it must not alter live trading, risk limits, API credentials, provider adapters, scraping policy, or model-approval controls.
