#!/usr/bin/env python3
"""
It's Only a Game - Sports Pipe

Pulls breaking sports news from a curated list of accounts via Apify,
classifies each item (transfer, result, manager change, quote, injury),
and reacts with a Paddy Power / Aldi-style take that fires stereotype
jokes when the news matches a known trigger.

Designed to run as a separate Threads account (@ItsOnlyAGamee) with its
own Typefully social set, completely independent of the AnywhereIncome
pipes.

Required secrets:
  ANTHROPIC_API_KEY
  APIFY_API_TOKEN
  TYPEFULLY_API_KEY
  TYPEFULLY_GAME_SOCIAL_SET_ID  (the It's Only a Game social set in Typefully)
  GITHUB_TOKEN                  (auto-provided by Actions)
"""

import os, re, sys, json, random, datetime, subprocess, requests
import anthropic

# --- env ---
ANTHROPIC_API_KEY        = os.environ["ANTHROPIC_API_KEY"]
APIFY_API_TOKEN          = os.environ["APIFY_API_TOKEN"]
TYPEFULLY_API_KEY        = os.environ["TYPEFULLY_API_KEY"]
TYPEFULLY_SOCIAL_SET_ID  = os.environ.get("TYPEFULLY_GAME_SOCIAL_SET_ID", "")

# --- config ---
SEED_HANDLES        = ["FabrizioRomano", "David_Ornstein", "BBCSport", "SkySportsNews"]
NEWS_LOOKBACK_HOURS = 12
POSTS_PER_RUN       = 6
MIN_NEWS_LENGTH     = 60
POSTED_LOG          = "posted_news.json"

NEWSLETTER_URL = ""  # not used here, no newsletter funnel for this brand yet


# --- voice profile, distilled from Paddy Power + Aldi scrape ---

SPORTS_SYSTEM_PROMPT = """You write short, punchy Threads posts for "It's Only a Game", a UK sports account that takes the piss out of football, F1, golf, tennis, NFL and the rest. Voice modelled on Paddy Power crossed with Aldi UK.

WHO YOU ARE
- A British sports fan with no allegiance to any club
- Chronically online, deadpan, slightly cocky
- Knowing wink with everything you say
- You mock fans, players, managers, pundits, and yourself in equal measure
- Your humour earns its laugh from a real news event, not from random observations

THE GOLDEN RULE
You react to a SPECIFIC news event the user gives you. Take that event, find the angle, deliver a 2-3 line take. NEVER write generic "us when..." posts about nothing. The news IS the post; you just frame it.

NON-NEGOTIABLE RULES (output is auto-rejected if you break any)

1. POST IS MAX 280 CHARACTERS. Hard cap.
2. POST IS 2-3 LINES MAX. Use \\n\\n between beats — every post longer than one short sentence MUST have at least one line break. Mobile reads like one wall of text otherwise. Example layout:
   "BREAKING: [news fact].\\n\\n[the dig]."
   Or: "[opening reaction line].\\n\\n[follow-up beat].\\n\\n[final line]."
3. NO EM DASHES (—). NO EN DASHES (–). Use commas, full stops, or colons.
4. NO HASHTAGS.
5. NEVER FABRICATE FACTS. The names, scores, transfers, and quotes in your post must come from the source news event you've been given. Do not invent player names, results, or quotes.
6. EVERY POST MUST CONNECT TO THE SOURCE NEWS. If you can't find a sharp angle on the news event, write a deadpan straight reaction rather than veering off-topic.

OPENER STYLES — mix across posts so the feed doesn't feel formulaic

A. NEWS HEADLINE (about 25% of posts) — lead with one of these and then ruin it:
   "BREAKING: ...", "JUST IN:", "HUGE NEWS:", "TEAM NEWS:", "RESULT:", "FULL-TIME:", "EXCLUSIVE:", "BOMBSHELL:", "UPDATE:"
   Example: "BREAKING: Michael Jackson appointed Burnley interim manager. He'll heal Turf Moor, make it a better place."

B. CONVERSATIONAL REACTION (about 35% of posts) — no prefix, just deliver the dig
   Example: "Arne Slot complaining that English clubs don't want to play football, then taking Liverpool to Paris with a back five. Funny."

C. QUOTE-MARK SARCASM (about 15% of posts) — let the quotes do the work
   Example: "FULL-TIME: Brighton 3-0 'Chelsea'."

D. ALL-CAPS OUTBURST (about 10% of posts) — Aldi-style emotional reaction
   Example: "ARSENAL'S TREBLE PARADE STATUS: cancelled, cancelled, ???, ???"

E. DEADPAN OBSERVATION (about 15% of posts) — straight-faced absurd take
   Example: "Liverpool fans really buying into the whole 'Emptyhad' thing by leaving in their droves after 60 minutes."

CLUB / FIGURE STEREOTYPES — fire ONLY when the news triggers them

Don't force these. Use only when the news pattern matches.

- SPURSY: triggered when Tottenham draw from a leading position, blow a lead, lose a derby, lose to lower-tier opposition, throw a cup tie, finish 4th when 1st was possible, sack a manager mid-stride. Joke = inevitability of Spurs being Spurs.
- ARSENAL BOTTLE: triggered when Arsenal slip in a title race, miss top four, lose a final, blow a lead, get knocked out of a competition late. Joke = parade-cancellation, treble dreams collapsing.
- MAN UTD CHAOS: triggered when Utd lose to a smaller club, sack a manager, have a transfer fall through, fans turn on the board, players underperform. Joke = "fans not from Manchester", Glazers, decline since Fergie.
- CITY EMPTY SEATS: triggered when City win comfortably, win another trophy, dominate a fixture. Joke = Etihad attendance, plastic, 115 charges, Pep substitutions.
- LIVERPOOL EXCUSES: triggered when Liverpool lose, especially when they leave early at away grounds. Joke = scousers blaming officials, Istanbul nostalgia, "we go again".
- CHELSEA OVERSPEND: triggered when Chelsea sign someone for a huge fee, sack a manager, lose despite massive squad. Joke = Boehly's transfer-window ADHD, 3-7-year contracts.
- WEST HAM BUBBLES: triggered when West Ham fans leave a stadium early, claret-and-blue army content. Joke = always near relegation, fans giving up halfway.
- LEEDS DRAMA: triggered on Leeds promotion/relegation/cup runs. Joke = the chaos energy, "Leeds are back".
- PEP TINKERING: triggered on weird City team selection, multiple substitutions, formation changes. Joke = defragging a hard drive, overthinking a simple problem.
- MOURINHO MELTDOWN: triggered when Mourinho or his current club loses. Joke = parking the bus, third-season decline, "I prefer not to speak".
- VAR FARCE: triggered on any controversial VAR decision. Joke = the tech ruining the game while pretending to fix it.
- F1 — HAMILTON ROBBED: triggered when Hamilton finishes badly. Joke = Abu Dhabi 2021 forever.
- F1 — VERSTAPPEN AGGRESSION: triggered on any Max overtake/incident. Joke = "running people off the road again".
- F1 — FERRARI STRATEGY: triggered on any Ferrari race outcome. Joke = "Box, box, box. Stay out. Box. Sorry, what?"
- TENNIS — BRITISH NUMBER 2: triggered on any British player not winning. Joke = polite acceptance of perpetual mid-tier.
- GOLF — LIV vs PGA: triggered on golf news. Joke = the money grab vs the tradition.
- NFL — JETS MISERY / COWBOYS CHOKE: triggered on those teams losing in big moments.

BANNED PHRASES (auto-rejected)
"Most people think...", "Here's the thing...", "The real play", "Plot twist:", "Real talk", "The bottom line", "The kicker", "This changes everything", "Imagine if...", "What if I told you...", "It's not about X, it's about Y" patterns. "Not X. Not Y." staccato. "X, not Y." antithesis tails. Three-part rhythmic lists. Single-word sentences for emphasis. Trailing ellipsis (...). Sports cliches: "absolute scenes", "what a moment", "level on points", "as it stands", "can't see past", "make no mistake".

OUTPUT
Valid JSON only. No code fences. No commentary. Use \\n\\n between lines for mobile spacing.
{"post": "the post text"}"""


# --- shared ban list (programmatic validation) ---

BANNED_SUBSTRINGS = [
    "but here's what", "here's the thing", "here's what nobody",
    "the paradox:", "the reality:", "the catch:", "the truth is",
    "the real play", "plot twist", "real talk", "the bottom line",
    "the kicker", "this changes everything", "most people think",
    "most people miss", "imagine if", "what if i told you",
    "the difference isn't just", "it's not about", "it's not just",
    "this isn't about", "this isn't just",
    # Sports clichés specifically
    "absolute scenes", "what a moment", "make no mistake",
    "as it stands", "can't see past", "talk about a",
]

BANNED_REGEX_PATTERNS = [
    (r"\bnot\s+\w+[.,]\s+not\s+\w+", "staccato 'Not X. Not Y.' pattern"),
    (r"\.{3,}.{0,30}$", "trailing or near-end ellipsis"),
    (r"\.{3,}\s*$", "ellipsis at end"),
    (r"\bone\s+\w+s?\s+.{2,30}\.\s+the\s+other\s+\w+s?\s+.{2,40}", "binary contrast pattern"),
    (r"\bno\s+\w+[.!]\s+no\s+\w+", "triple-fragment 'No X. No Y.' rhythm"),
    (r",\s+not\s+\w+\.\s*$", "antithesis tail ', not Y.' at end of post"),
    (r"\b(on|by|with|for|in|of|to|and|but|or|the|a|an|that|which|from|as|at|into|onto|upon|via|though)\.\s*$",
     "stealth cliffhanger (post ends mid-thought)"),
    # "That's not X. That's Y." / "That's not X, that's Y." — common AI antithesis
    (r"\bthat'?s\s+not\s+.{2,40}[,.]\s+that'?s\s+", "'That's not X. That's Y.' antithesis"),
    # "It's not X. It's Y."
    (r"\bit'?s\s+not\s+.{2,40}[,.]\s+it'?s\s+", "'It's not X. It's Y.' antithesis"),
    # Fragment-then-explanation: "Two years. That's how long..." / "Five goals. That's what happens..."
    (r"\b\w+\s+\w+\.\s+that'?s\s+(how|what|why|when|where)\s+", "fragment-then-explanation auto-rhythm"),
]


# --- state ---

def load_posted_log():
    if not os.path.exists(POSTED_LOG):
        return {"news_ids": []}
    try:
        with open(POSTED_LOG) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"news_ids": []}


def save_posted_log(log):
    log["news_ids"] = log["news_ids"][-500:]
    with open(POSTED_LOG, "w") as f:
        json.dump(log, f, indent=2)


# --- apify ---

def fetch_news(handles, hours=NEWS_LOOKBACK_HOURS):
    """Pull recent tweets from sports news handles via Apify."""
    since_dt = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    since_date = since_dt.strftime("%Y-%m-%d")
    payload = {
        "twitterHandles": handles,
        "maxItems": 50,  # over-fetch for filtering
        "sort": "Latest",
        "tweetLanguage": "en",
        "start": since_date,
    }
    print(f"Fetching news from {handles} since {since_date}...")
    r = requests.post(
        "https://api.apify.com/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items",
        params={"token": APIFY_API_TOKEN, "format": "json"},
        json=payload,
        timeout=120,
    )
    if r.status_code not in (200, 201):
        print(f"  Apify error {r.status_code}: {r.text[:300]}")
        return []
    items = r.json()
    print(f"  Got {len(items)} items back.")
    return items


def normalise_news(t):
    """Pull text + metadata defensively from apidojo schema."""
    text = t.get("text") or t.get("fullText") or t.get("full_text") or ""
    return {
        "id": str(t.get("id") or t.get("tweetId") or t.get("rest_id") or ""),
        "text": text.strip(),
        "url": t.get("url") or t.get("twitterUrl") or "",
        "author": (t.get("author") or {}).get("userName") or t.get("username") or "",
        "created_at": t.get("createdAt") or t.get("created_at") or "",
        "likes": int(t.get("likeCount") or t.get("favorite_count") or 0),
        "type": (t.get("type") or "").lower(),
    }


def filter_usable_news(items, used_ids):
    """Keep only fresh, substantive original tweets."""
    out = []
    rejected = {"no_id": 0, "already_used": 0, "too_short": 0, "rt_or_reply": 0}

    for raw in items:
        n = normalise_news(raw)
        if not n["id"]:
            rejected["no_id"] += 1
            continue
        if n["id"] in used_ids:
            rejected["already_used"] += 1
            continue
        if not n["text"] or len(n["text"]) < MIN_NEWS_LENGTH:
            rejected["too_short"] += 1
            continue
        if n["type"] in ("retweet", "reply") or n["text"].startswith("RT @") or n["text"].startswith("@"):
            rejected["rt_or_reply"] += 1
            continue
        out.append(n)

    if not out:
        print(f"  Rejection breakdown: {rejected}")
    out.sort(key=lambda x: x["likes"], reverse=True)
    return out


# --- generation ---

def validate_post(post):
    problems = []
    if len(post) > 280:
        problems.append(f"is {len(post)} chars, max 280")
    if "—" in post:
        problems.append("contains em dash (—)")
    if "–" in post:
        problems.append("contains en dash (–)")
    # Strict line-spacing: any post over 80 chars must have at least one \n\n break
    if len(post) > 80 and "\n\n" not in post:
        problems.append("missing line break (use \\n\\n between beats; one or two breaks for readability on mobile)")
    # Two-three lines: count non-empty paragraphs separated by \n\n
    paragraphs = [p for p in post.split("\n\n") if p.strip()]
    if len(paragraphs) > 3:
        problems.append(f"has {len(paragraphs)} paragraphs, max 3")
    lower = post.lower()
    for phrase in BANNED_SUBSTRINGS:
        if phrase in lower:
            problems.append(f"contains banned phrase: '{phrase}'")
    for pattern, description in BANNED_REGEX_PATTERNS:
        if re.search(pattern, post, flags=re.IGNORECASE):
            problems.append(f"matches banned pattern: {description}")
    return len(problems) == 0, problems


def sanitize_post(post):
    post = post.replace("—", ", ").replace("–", ", ")
    post = re.sub(r"\.{3,}\s*$", ".", post.rstrip())
    post = re.sub(r"\.{3,}.{0,30}$", ".", post.rstrip())
    if len(post) > 280:
        post = post[:279].rsplit(" ", 1)[0]
        if not post.endswith((".", "!", "?")):
            post += "."
    return post.rstrip()


def generate_post_from_news(news_item):
    """Generate one short post reacting to a news item."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    source = (
        f"News source: @{news_item['author']}\n\n"
        f"News content:\n{news_item['text']}\n\n"
        f"Source URL: {news_item['url']}"
    )

    base_msg = (
        f"{source}\n\n"
        f"Write ONE short Threads post reacting to this news. 2-3 lines max. "
        f"Pick the sharpest angle. Use a stereotype joke ONLY if the news triggers one naturally. "
        f"Output the JSON object."
    )

    last_post = None
    feedback = ""

    for attempt in range(3):
        msg = base_msg
        if feedback:
            msg = (
                f"YOUR PREVIOUS ATTEMPT FAILED THESE CHECKS:\n{feedback}\n\n"
                f"Rewrite the post with all problems fixed. Stay 2-3 lines. Anchor on the actual news.\n\n" + msg
            )

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=SPORTS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": msg}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)

        try:
            data = json.loads(raw)
            post = data["post"]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  Parse error attempt {attempt + 1}: {e}")
            print(f"  Raw output: {raw[:300]}")
            continue

        last_post = post
        ok, problems = validate_post(post)
        if ok:
            return post

        print(f"  Validation failed (attempt {attempt + 1}):")
        for p in problems:
            print(f"    - {p}")
        feedback = "\n".join(f"- {p}" for p in problems)

    if last_post:
        sanitized = sanitize_post(last_post)
        ok, _ = validate_post(sanitized)
        if ok:
            print("  Sanitised and shipping.")
            return sanitized
        print("  Failed even after sanitising. Dropping.")
    return None


# --- typefully ---

def get_typefully_social_set():
    if TYPEFULLY_SOCIAL_SET_ID:
        return TYPEFULLY_SOCIAL_SET_ID
    print("  TYPEFULLY_GAME_SOCIAL_SET_ID not set, querying Typefully...")
    r = requests.get(
        "https://api.typefully.com/v2/social-sets",
        headers={"Authorization": f"Bearer {TYPEFULLY_API_KEY}"},
        timeout=15,
    )
    if r.status_code != 200:
        print(f"  Typefully social-sets error {r.status_code}: {r.text[:200]}")
        return None
    sets = r.json().get("results", [])
    if not sets:
        return None
    print("  Available social sets:")
    for s in sets:
        print(f"    {s['id']}: {s.get('name', 'unnamed')} (@{s.get('username', '')})")
    return sets[0]["id"]


def push_to_typefully(post_text):
    social_set_id = get_typefully_social_set()
    if not social_set_id:
        return None

    # Try a few platform key names since Typefully's docs are sparse and the API rebranded
    platform_keys_to_try = ["x", "twitter_x", "twitter"]

    for platform_key in platform_keys_to_try:
        r = requests.post(
            f"https://api.typefully.com/v2/social-sets/{social_set_id}/drafts",
            headers={
                "Authorization": f"Bearer {TYPEFULLY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "platforms": {
                    platform_key: {
                        "enabled": True,
                        "posts": [{"text": post_text}],
                    }
                }
            },
            timeout=15,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return data.get("share_url") or data.get("id")
        # If 422 with "extra_forbidden", that key isn't valid — try the next
        if r.status_code == 422 and "extra_forbidden" in r.text:
            print(f"  Platform key '{platform_key}' rejected, trying next...")
            continue
        # Any other error, log and stop
        print(f"  Typefully draft error {r.status_code}: {r.text[:300]}")
        return None

    # All platform keys failed — try without the platforms wrapper at all
    print("  All platform keys rejected. Trying minimal payload...")
    r = requests.post(
        f"https://api.typefully.com/v2/social-sets/{social_set_id}/drafts",
        headers={
            "Authorization": f"Bearer {TYPEFULLY_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"text_to_tweet": post_text},
        timeout=15,
    )
    if r.status_code in (200, 201):
        data = r.json()
        return data.get("share_url") or data.get("id")
    print(f"  Final fallback failed: {r.status_code}: {r.text[:300]}")
    return None


# --- commit ---

def commit_state():
    if not os.path.exists(POSTED_LOG):
        return
    subprocess.run(["git", "config", "user.name", "Sports Pipe Bot"], check=True)
    subprocess.run(["git", "config", "user.email", "bot@noreply"], check=True)
    subprocess.run(["git", "add", POSTED_LOG], check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode
    if diff == 0:
        return
    msg = f"Sports pipe run: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    subprocess.run(["git", "commit", "-m", msg], check=True)
    for attempt in range(3):
        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        if result.returncode == 0:
            return
        print(f"  Push attempt {attempt + 1} failed: {result.stderr[:200]}")
        subprocess.run(["git", "pull", "--rebase", "--autostash"], check=False)


# --- main ---

def main():
    print("=" * 55)
    print("  It's Only a Game - Sports Pipe")
    print(f"  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Seeds: {', '.join(SEED_HANDLES)}")
    print(f"  Target: {POSTS_PER_RUN} posts this run")
    print("=" * 55)

    posted_log = load_posted_log()
    used_ids = set(posted_log.get("news_ids", []))

    raw_items = fetch_news(SEED_HANDLES)
    if not raw_items:
        print("\nNo news returned. Exiting cleanly.")
        sys.exit(0)

    usable = filter_usable_news(raw_items, used_ids)
    print(f"\nUsable news items: {len(usable)}")

    if not usable:
        print("Nothing fresh to react to. Exiting cleanly.")
        sys.exit(0)

    drafts_pushed = 0

    for news in usable[:POSTS_PER_RUN]:
        print(f"\n{'-'*55}")
        print(f"  @{news['author']} ({news['likes']} likes)")
        print(f"  \"{news['text'][:120]}{'...' if len(news['text']) > 120 else ''}\"")

        post = generate_post_from_news(news)
        if not post:
            print("  No valid post, skipping.")
            continue

        preview = post.replace("\n", " ")[:80]
        print(f"\n  Post ({len(post)} chars): {preview}...")

        tid = push_to_typefully(post)
        if tid:
            drafts_pushed += 1
            print(f"    Typefully draft: {tid}")
            posted_log["news_ids"].append(news["id"])
        else:
            print("    Failed to push to Typefully.")

    save_posted_log(posted_log)
    commit_state()

    print(f"\n{'='*55}")
    print(f"[OK] Sports pipe done.")
    print(f"     News items considered: {len(usable[:POSTS_PER_RUN])}")
    print(f"     Drafts pushed: {drafts_pushed}")


if __name__ == "__main__":
    main()
