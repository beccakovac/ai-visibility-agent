import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from google.genai import errors

from agent import NUM_QUESTIONS, QuotaExhausted, run_audit
from site_check import normalize_url

# Google's free tier allows about 20 requests per model per day, and each live run uses 3,
# so the whole app shares a small daily cap that leaves room for retries.
DAILY_LIVE_RUNS = 8
SHOWCASE_DIR = Path(__file__).parent / "showcase"
ACCENT = "#2a78d6"  # the brand being audited
MUTED = "#a3a19a"  # its competitors

st.set_page_config(page_title="AI Visibility Agent", page_icon="📡")


@st.cache_resource
def live_run_counter():
    """One counter shared by everyone using the app. It starts again when the app restarts."""
    return {"day": None, "runs": 0}


def runs_left_today():
    # Google's free allowance resets at midnight Pacific time, so the cap does too.
    today = (datetime.now(timezone.utc) - timedelta(hours=8)).date()
    counter = live_run_counter()
    if counter["day"] != today:
        counter.update(day=today, runs=0)
    return DAILY_LIVE_RUNS - counter["runs"]


def get_api_key():
    """Reads the Gemini API key from secrets, without ever showing it on screen."""
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except FileNotFoundError:
        return ""


def load_showcase():
    """Loads the saved sample audits, so visitors see real results instantly with no API call."""
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SHOWCASE_DIR.glob("*.json"))]


def share_of_voice_chart(result):
    data = pd.DataFrame(result["scores"]).sort_values("share_of_voice", ascending=False)
    data["who"] = ["Your brand" if b == result["brand"] else "Competitor" for b in data["brand"]]
    data["label"] = data["share_of_voice"].map(lambda v: f"{v:g}%")
    base = alt.Chart(data).encode(
        y=alt.Y("brand:N", sort=list(data["brand"]), title=None, axis=alt.Axis(labelFontSize=13, ticks=False, domain=False)),
        x=alt.X("share_of_voice:Q", title="AI share of voice (%)", scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(grid=True, gridOpacity=0.3, tickCount=5)),
    )
    bars = base.mark_bar(cornerRadiusEnd=4, height=26).encode(
        color=alt.Color("who:N", scale=alt.Scale(domain=["Your brand", "Competitor"], range=[ACCENT, MUTED]),
                        legend=None),
        tooltip=[
            alt.Tooltip("brand:N", title="Brand"),
            alt.Tooltip("share_of_voice:Q", title="Share of voice (%)"),
            alt.Tooltip("mentions:Q", title=f"Answers mentioning it (of {len(result['answers'])})"),
            alt.Tooltip("named_first:Q", title="Times named first"),
        ],
    )
    labels = base.mark_text(align="left", dx=6, fontSize=13).encode(text="label:N")
    return (bars + labels).properties(height=60 * len(data))


def render_results(result):
    brand = result["brand"]
    mine = next(s for s in result["scores"] if s["brand"] == brand)
    site = result["site"]
    total = len(result["answers"])

    st.subheader(f"{brand} in AI answers")
    st.caption(
        f"{result['category']} · vs. {', '.join(result['competitors'])} · "
        f"asked {result['model']} on {result['run_date']}"
    )

    cols = st.columns(4)
    cols[0].metric("AI share of voice", f"{mine['share_of_voice']:g}%")
    cols[1].metric("Mentioned in", f"{mine['mentions']} of {total}")
    cols[2].metric("Named first", f"{mine['named_first']} times")
    cols[3].metric("AI-readiness", f"{site['score']} of {len(site['checks'])}" if site else "n/a")

    st.info(result["plan"]["verdict"])

    st.markdown("#### Share of voice")
    st.altair_chart(share_of_voice_chart(result), width="stretch")
    st.caption(
        "In each answer, the first brand named earns 1 point, the second ½, the third ⅓, and so on. "
        "Share of voice is each brand's slice of the points. Hover a bar for details."
    )

    # Skip the tracked brands, including longer versions of their names (like "Zenni Optical" for "Zenni").
    tracked = [t.lower() for t in [brand] + result["competitors"]]
    others = Counter(
        b for a in result["answers"] for b in a.get("all_brands", [])
        if not any(t == b.lower() or (len(t) > 3 and (t in b.lower() or b.lower() in t)) for t in tracked)
    )
    sources = Counter(s for a in result["answers"] for s in a.get("sources", []))
    left, right = st.columns(2)
    with left:
        st.markdown("#### Other brands the AI recommends")
        if others:
            st.markdown("\n".join(f"- **{b}** ({n} answer{'s' * (n > 1)})" for b, n in others.most_common(6)))
        else:
            st.caption("None beyond the brands you entered.")
    with right:
        st.markdown("#### Where the AI sends people")
        if sources:
            st.markdown("\n".join(f"- **{s}** ({n})" for s, n in sources.most_common(6)))
            st.caption("Getting covered on these is a strong lever for AI visibility.")
        else:
            st.caption("The answers didn't point to any review sites or publications.")

    st.markdown("#### Fixes, most important first")
    for i, fix in enumerate(result["plan"]["fixes"], start=1):
        with st.expander(f"{i}. {fix['title']}  ·  Impact: {fix['impact']} · Effort: {fix['effort']}", expanded=i == 1):
            st.markdown(f"**Why it matters:** {fix['why_it_matters']}\n\n**How to fix it:** {fix['how_to_fix']}")

    st.markdown("#### Website AI-readiness")
    if site:
        for check in site["checks"]:
            icon = "✅" if check["passed"] else "⚠️" if check["passed"] is None else "❌"
            st.markdown(f"{icon} **{check['name']}**: {check['detail']}")
    else:
        st.caption("The homepage couldn't be loaded (some sites block automated visitors), so these checks were skipped.")

    st.markdown("#### Ready-to-paste fixes")
    st.caption("Fill in anything in [square brackets] before publishing.")
    with st.expander("FAQ answers for your website"):
        st.markdown("\n\n".join(f"**{f['question']}**\n\n{f['answer']}" for f in result["plan"]["faqs"]))
    with st.expander("Schema markup (JSON-LD): paste into your homepage's <head>"):
        for block in result["json_ld"]:
            st.code(block, language="html")
    with st.expander("llms.txt: save at yourdomain.com/llms.txt"):
        st.code(result["plan"]["llms_txt"], language="markdown")
    if result["robots_snippet"]:
        with st.expander("robots.txt: let AI crawlers back in"):
            st.code(result["robots_snippet"], language="text")

    st.markdown("#### The questions and answers")
    st.caption("The AI was told to answer each question as if it came from a different shopper in a new conversation.")
    for a in result["answers"]:
        named = ", ".join(a["tracked_mentions"]) or "none of the tracked brands"
        with st.expander(f"{'✅' if brand in a['tracked_mentions'] else '⚪'} {a['question']}"):
            st.caption(f"Intent: {a['intent']} · Mentioned: {named}")
            st.markdown(a["answer"])

    st.download_button(
        "Download results (JSON)",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name=f"ai-visibility-{brand.lower().replace(' ', '-')}.json",
        mime="application/json",
    )


st.title("AI Visibility Agent")
st.write(
    "When people ask ChatGPT or Gemini *\"what's the best…?\"*, which brands get recommended? "
    "This agent asks an AI the questions your buyers ask, scores your **share of voice** against competitors, "
    "checks whether your website is easy for AI to read, and writes the fixes."
)

showcase_tab, live_tab, how_tab = st.tabs(["Showcase", "Run your own", "How it works"])

with showcase_tab:
    samples = load_showcase()
    if not samples:
        st.caption("No sample audits saved yet.")
    else:
        st.caption("Real audits, run once and saved, so they load instantly.")
        choice = st.radio(
            "Sample brand", [s["brand"] for s in samples], horizontal=True, label_visibility="collapsed"
        )
        render_results(next(s for s in samples if s["brand"] == choice))

with live_tab:
    api_key = get_api_key()
    left_today = runs_left_today()
    # Filled in at the end, so the count is current after a run.
    allowance = st.empty()
    st.caption("Please don't enter anything confidential: Google may use free-tier requests to improve its products.")

    with st.form("audit"):
        brand = st.text_input("Brand name", placeholder="Allbirds")
        raw_url = st.text_input("Website", placeholder="allbirds.com")
        category = st.text_input("What they sell", placeholder="sustainable sneakers")
        competitor_cols = st.columns(3)
        competitors = [
            col.text_input(f"Competitor {i}", placeholder=("Veja", "Cariuma", "Rothy's")[i - 1] + (" (optional)" if i == 3 else ""))
            for i, col in enumerate(competitor_cols, start=1)
        ]
        submitted = st.form_submit_button("Run the agent", type="primary")

    if submitted:
        url = normalize_url(raw_url)
        competitors = [c.strip() for c in competitors if c.strip()]
        if not (brand.strip() and category.strip()):
            st.error("Add a brand name and what they sell.")
        elif not url:
            st.error("That website doesn't look right. Try something like allbirds.com")
        elif len(competitors) < 2:
            st.error("Add at least two competitors, so there's someone to compare against.")
        elif not api_key:
            st.warning("Live runs need a Gemini API key in .streamlit/secrets.toml. The Showcase tab works without one.")
        elif left_today <= 0:
            st.warning("Today's free audits are all used up. They reset at midnight Pacific time. Meanwhile, the Showcase tab has full sample results.")
        else:
            live_run_counter()["runs"] += 1
            try:
                with st.status("The agent is working...", expanded=True) as status:
                    result = run_audit(api_key, brand.strip(), url, category.strip(), competitors, on_step=st.write)
                    status.update(label="Done", state="complete", expanded=False)
                st.session_state.live_result = result
            except QuotaExhausted:
                st.warning(
                    "Google's free daily allowance for this demo has run out. It resets at midnight Pacific time. "
                    "Meanwhile, the Showcase tab has full sample results."
                )
            except errors.ClientError as e:
                st.error(
                    "Google rejected the API key. Check it in your secrets."
                    if e.code in (400, 401, 403) and "key" in str(e.message).lower()
                    else f"Gemini returned an error ({e.code}). Try again in a moment."
                )
            except errors.ServerError:
                st.error("Gemini is very busy right now (this happens on Google's side). Try again in a few minutes.")
            except ValueError:
                st.error("Gemini had a hiccup partway through. Try again in a moment.")

    allowance.write(
        f"Takes about a minute. Runs on Google's free Gemini tier, so there's a shared limit of "
        f"{DAILY_LIVE_RUNS} audits a day ({max(runs_left_today(), 0)} left today)."
    )

    if "live_result" in st.session_state:
        render_results(st.session_state.live_result)

with how_tab:
    st.markdown(f"""
**The agent works in five steps:**

1. **Checks the website** for the signals AI assistants rely on, reading the raw page the way AI crawlers do (most don't run JavaScript): whether AI crawlers are allowed in robots.txt, structured data (JSON-LD), FAQ content, an llms.txt file, and a clear title and description. This part is plain code, so it's free and gives the same answer every time.
2. **Writes {NUM_QUESTIONS} buyer questions** for the category, like *"best running shoes for flat feet under $150"*. It never names the brands, so the AI has to recommend someone on its own.
3. **Asks the AI the questions**, telling it to answer each one as if it came from a different person in a brand-new conversation. The AI also lists every brand and source it mentioned.
4. **Keeps score.** Code (not AI) finds which tracked brands each answer names and in what order, then calculates share of voice.
5. **Writes the fixes**: a prioritized plan, plus FAQ answers, schema markup, and an llms.txt file ready to paste.

**Worth knowing:** answers come from Gemini's built-in knowledge, with live web search turned off. That shows what the AI has *learned* about a category, which is the foundation of AI visibility. AI answers vary from run to run, so treat the score as a snapshot, not a verdict.
""")
