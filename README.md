# AI Visibility Agent

**When someone asks an AI assistant "what's the best…?", does your brand come up?** This agent finds out. It asks an AI the questions your buyers ask, measures your share of voice against competitors, checks whether your website is easy for AI to read, and hands you the fixes, ready to paste.

### ▶ Live demo: coming soon on Streamlit Community Cloud

---

## Why this exists

Search is quietly moving into chat. More and more buyers skip the ten blue links and ask ChatGPT, Gemini, or Claude for a shortlist. That shortlist is the new page one, and most brands have no idea whether they're on it.

Making a brand show up there is called **answer engine optimization (AEO)**. I started by doing it for my own site, [beccakovac.com](https://www.beccakovac.com/): structured data, an FAQ, an `llms.txt` file, and a robots.txt that welcomes AI crawlers. Then I built an agent that does the audit for any brand.

It's the sequel to my [CRO Auditor](https://cro-auditor-becca.streamlit.app). CRO Auditor helps a page convert the visitors it gets. This one helps a brand get recommended in the first place.

**Who it's for:** marketers, founders, and agencies who want a fast, evidence-based read on their AI visibility, plus a concrete to-do list rather than a vague "optimize for AI."

## What you get

Enter a brand, its website, what it sells, and two or three competitors. About a minute later:

| Section | What it tells you |
|---|---|
| **AI share of voice** | How much of the AI's recommendations go to you vs. each competitor, shown as a chart |
| **Mentions and first place** | How many answers named you at all, and how often you were the first brand named |
| **Other brands the AI recommends** | Competitors you didn't list but the AI keeps bringing up |
| **Where the AI sends people** | The review sites and publications the AI tells buyers to check: your PR shortlist |
| **Fixes, ranked by impact** | Five to seven changes, each tied to evidence, with impact and effort ratings |
| **Website AI-readiness** | Six pass/fail checks: AI crawler access, JSON-LD schema, Organization schema, FAQ content, llms.txt, and title/description |
| **Ready-to-paste fixes** | FAQ answers, valid JSON-LD schema markup, a draft llms.txt file, and robots.txt lines if crawlers are blocked |
| **The receipts** | Every question and the AI's full answer, so you can see exactly where the numbers came from |

**Showcase mode** has three sample audits (Allbirds, Oatly, and HubSpot), run once and saved, so they load instantly and cost nothing to view.

## How it works

The agent runs five steps, and each job goes to whatever does it best. The AI handles language. Plain code handles anything that needs to be exact and repeatable.

1. **Checks the website (code).** It reads the homepage, robots.txt, and llms.txt the way an AI crawler does: raw HTML, no JavaScript. That matters because most AI crawlers don't run JavaScript, so schema that only appears after scripts run is invisible to them.
2. **Writes buyer questions (AI).** Gemini writes eight realistic questions across different intents: "best for a need," comparisons, alternatives, value for money, and problems to solve. It's told never to name the brands, so the AI has to recommend someone on its own.
3. **Asks the questions (AI).** Gemini answers all eight in one request, told to treat each as if it came from a different person in a brand-new conversation. Alongside each answer, it lists every brand and source it mentioned, returned as structured data rather than free text.
4. **Keeps score (code).** Code finds which tracked brands each answer names and in what order. The first brand named earns 1 point, the second ½, the third ⅓, and so on, because being recommended first matters more, just like ranking first on Google. Share of voice is each brand's slice of the points.
5. **Writes the fixes (AI + code).** Gemini writes the prioritized plan, FAQ answers, and llms.txt, using only facts from the homepage, with [placeholders] wherever it would otherwise have to guess. Code then assembles the JSON-LD, so the schema is always valid.

## Choices worth explaining

- **It costs $0 to run.** It uses Google's free Gemini tier, which allows about 20 requests per model per day. That's tight, so a full audit uses just three requests: one to write the questions, one to answer them all, and one to write the fixes. Live runs share a daily cap, and Showcase mode means visitors always see full results, even when the free allowance runs out.
- **Batched questions, a deliberate trade-off.** The most realistic test would ask each question in its own conversation, but that takes eleven requests per audit, which is barely one audit a day on the free tier. Instead, the AI answers all eight at once and is told to treat each as a separate shopper. It's a little less like real life, and the extra capacity is worth it.
- **No live web search, on purpose.** Gemini can search Google before answering, but Google's terms don't allow analyzing or saving search-backed answers, which is exactly what a share-of-voice tool does. So the agent measures what the AI has *learned* about a category. That's the foundation of AI visibility, and it's what assistants fall back on whenever they don't search.
- **A backup model.** Free-tier models get busy, and each one has its own daily allowance. If the main model is overloaded or out of requests, the agent switches to a lighter backup. All eight answers arrive in a single request, so they always come from the same model, and the results show which one answered.
- **The scraped website is treated as data, never instructions.** Web pages can contain text aimed at AI ("ignore your instructions and…"). The prompts fence page content off and tell the model to review it, not obey it.
- **The math lives in code, not the AI.** Language models are great writers and unreliable counters. Keeping the scoring in plain code means the same answers always produce the same score, and anyone can check it.

## Limitations

- **Batched, not separate chats.** The AI answers all eight questions in one request. It's told to treat each one independently, but it isn't a perfect stand-in for eight separate conversations.
- **AI answers vary.** Ask the same question twice and you may get a different list. Treat a score as a snapshot, and compare runs over time instead of reading too much into one.
- **One AI model.** It measures Gemini. ChatGPT, Claude, and Perplexity each have their own opinions.
- **Brand names that are everyday words** (like "On" or "Dove") can occasionally be counted when a sentence starts with that word.
- **Homepage only.** The readiness checks look at the homepage, not every page on the site. Some sites block automated visitors, and when that happens the check is marked "couldn't check" instead of guessing.
- **A simple daily cap.** The live-run counter starts over whenever the app restarts. Google's own daily limit is the real backstop, and the app explains it in plain English when it's reached.
- Google may use free-tier requests to improve its products, so don't enter anything confidential.

## Built with

- [Streamlit](https://streamlit.io): the web interface
- [Google Gemini API](https://ai.google.dev/) (Gemini 3.6 Flash, with Gemini 3.5 Flash-Lite as a backup, both on the free tier): question writing, answers, and the fix plan, with structured JSON output
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/): reading web pages
- [Altair](https://altair-viz.github.io/): the share-of-voice chart

## Run it on your own computer

You'll need Python 3.10 or newer and a free [Gemini API key](https://aistudio.google.com/apikey).

```bash
git clone https://github.com/beccakovac/ai-visibility-agent.git
cd ai-visibility-agent
python -m venv .venv
```

Activate the environment (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on Mac/Linux), then:

```bash
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste your API key between the quotes. That file is in `.gitignore`, so your key is never committed. Then start the app:

```bash
streamlit run app.py
```

To refresh the Showcase samples, run `python make_showcase.py`. It uses 3 free requests per brand.

---

Built by [Rebecca Kovacevich](https://www.beccakovac.com/), AI growth marketing strategist and CRO consultant.
