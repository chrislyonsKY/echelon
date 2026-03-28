# Disclaimer

## General

Echelon is an open-source intelligence (OSINT) research tool provided **"as is"** under the Apache 2.0 license, without warranty of any kind, express or implied. Use of this software is entirely at your own risk.

This tool is intended for **lawful OSINT research, journalism, academic analysis, and humanitarian monitoring**. It is not a substitute for professional intelligence analysis, and its outputs should not be treated as ground truth.

## Data Accuracy

- All data is sourced from **publicly available open sources**. No classified, restricted, or proprietary intelligence feeds are used.
- Signal accuracy, completeness, and timeliness depend entirely on upstream data providers (GDELT, OpenSky, Global Fishing Watch, NASA FIRMS, etc.).
- Convergence Z-scores are **statistical indicators** derived from historical baselines. A high score means multiple signals are elevated relative to that location's history -- it does not confirm that a specific event has occurred.
- Geocoding is approximate. News articles and social media posts are geolocated using city-name matching, which may place signals in the wrong location.

## AI Copilot

- The AI copilot uses third-party language models (Anthropic Claude, OpenAI, Google Gemini, or self-hosted Ollama). AI-generated analysis **may contain errors, hallucinations, or outdated information**.
- The copilot is a research assistant, not an analyst. Always verify AI outputs against primary sources.
- BYOK (Bring Your Own Key): your API key is sent directly to your chosen provider. Echelon does not log, store, or inspect API keys unless you explicitly opt into encrypted server-side storage.

## Acceptable Use

This tool must **not** be used for:

- Targeting individuals or groups for harm
- Surveillance of private individuals
- Offensive military or intelligence operations
- Any activity that violates applicable local, national, or international law
- Circumventing access controls or terms of service of upstream data providers

Users are solely responsible for ensuring their use of Echelon complies with all applicable laws and regulations in their jurisdiction.

## Social Media & Web Scraping

- All social media data is collected from **publicly accessible** pages and feeds (public Telegram channels, public Reddit posts, public RSS feeds, etc.).
- No private messages, protected accounts, or login-walled content is accessed.
- Dark web monitoring uses **clearnet aggregator mirrors only** (e.g., RansomWatch GitHub). Echelon never connects to .onion addresses.
- Scraping behavior respects rate limits and robots.txt where applicable.

## No Affiliation

Echelon is an independent open-source project. It is **not affiliated with, endorsed by, or connected to** any government agency, military organization, intelligence service, or law enforcement body.

## Limitation of Liability

To the maximum extent permitted by law, the authors and contributors of Echelon shall not be liable for any direct, indirect, incidental, special, or consequential damages arising from the use of or inability to use this software, including but not limited to loss of data, business interruption, or decisions made based on Echelon's outputs.
