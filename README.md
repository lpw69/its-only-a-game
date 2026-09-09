# It's Only a Game

Automated content engine for [@ItsOnlyAGamee](https://www.threads.com/@ItsOnlyAGamee) on Threads.

Pulls breaking sports news from Fabrizio Romano, David Ornstein, BBC Sport and Sky Sports News every few hours, runs each item through a Paddy Power / Aldi-flavoured prompt, and pushes the resulting one-liner takes to Typefully as drafts ready to publish or schedule.

Publishing is **Threads-only** (the account's X profile is suspended, so the X platform is disabled in the Typefully payload).

## Architecture

```
Apify (X scraper) → Claude Haiku (voice) → style validator → Claude Sonnet (fact gate) → Typefully → Threads
```

Single Python script, single GitHub Actions workflow.

## Matched betting offer posts (monetization)

Once per day (first run at/after 16:00 UTC), the pipe posts one matched betting
offer post alongside the banter: a current bookmaker new-customer offer, the
rough profit lockable from it, and "Full walkthrough: link in bio" — so **keep
the OddsMonkey affiliate link in the Threads bio**.

How it's sourced, fully automated:

1. `fetch_offers` pulls a public offers page (Team Profit's welcome offers
   list, falling back to Matched Betting Blog) and strips it to text.
2. **Claude Sonnet** extracts the live sign-up offers as structured JSON
   (bookmaker, offer, estimated profit — the page's own figure, or 75% of the
   free bet value). LLM extraction instead of CSS selectors, so site redesigns
   don't break it.
3. The highest-value offer not featured in the last 21 days is picked
   (`offers_posted` in `posted_news.json` tracks this).
4. Haiku writes the hook in the account voice, the style validator runs, plus
   offer-specific bans: no "guaranteed", "risk-free", "no risk" or "free money"
   (ASA has upheld complaints against exactly those claims in matched betting
   promotion). The footer appends a plain-text "18+ | GambleAware" line to every offer post (no URL, so Threads renders no preview card).
5. The same Sonnet fact gate checks every figure in the hook against the
   extracted offer before publishing. Anything that can't pass is dropped —
   the slot just retries on the next run of the day.

If the offer sites are down or list nothing fresh, no offer post goes out that
day. The banter posts are unaffected.

## Fact checking

Haiku writes the joke, but Haiku's training data is stale — it will happily say a
player is at a club he left two seasons ago, invent a nationality, or fire an
"Arsenal bottle" joke on a day Arsenal actually won. To stop that, every post that
clears the style validator is run through a second model (**Claude Sonnet**, in
`fact_check_post`) that sees *only* the source tweet plus the generated post and
judges two things:

1. Does every checkable claim in the post (club, nationality, score, who won, who
   was signed/sacked) follow from the source tweet? It is told to use **no outside
   knowledge** — if the source doesn't establish it, the post may not assert it.
2. Does the joke's premise match what actually happened? (No mocking a team for
   losing when the source says they won.)

A post that fails is fed the rejection reason and regenerated (up to 3 attempts);
if it still can't pass, it is **dropped rather than published**. On a fact-gate API
error the post is treated as unsafe and dropped — the pipe never publishes an
unchecked post. Every post that does go out is recorded (source + text) under
`posts` in `posted_news.json` so you can audit what the account is saying.

## Voice

Modelled on Paddy Power's sports-reactive deadpan crossed with Aldi UK's chronically-online energy. Stereotype banks fire conditionally on news patterns:
- Spursy (blow-a-lead, derby loss, cup throw)
- Arsenal bottle (parade-cancellation, top-four slip)
- Man Utd chaos (Glazers, fans not from Manchester)
- City empty seats (Etihad attendance, 115 charges)
- Liverpool excuses (Istanbul nostalgia, ref blame)
- Pep tinkering (defragging-a-hard-drive substitutions)
- VAR farce, Mourinho meltdown, Hamilton-robbed, Ferrari strategy, etc.

Stereotypes only fire when the news pattern triggers them. No forced jokes.

## Post auditing

After each post goes out via Typefully, the pipe polls the draft for its live
Threads permalink (`threads_published_url` — publishing is async, so it waits
up to ~2 min) and records it alongside the source and post text in
`posted_news.json`, so you can review what the account is publishing without
watching the feed.

## Files

- `sports_pipe.py` — single script: scrape, classify, generate, validate, push
- `.github/workflows/sports_pipe.yml` — runs at 8am / 12pm / 5pm / 9pm UTC daily

## Required secrets

Set in Settings → Secrets and variables → Actions:

| Secret | What |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `APIFY_API_TOKEN` | Apify token (for the X tweet scraper) |
| `TYPEFULLY_API_KEY` | Typefully API key |
| `TYPEFULLY_GAME_SOCIAL_SET_ID` | The Typefully social set ID for `@ItsOnlyAGamee` (currently `302659`) |

## Running

Manual trigger:
```
Actions → It's Only a Game - Sports Pipe → Run workflow
```

Or wait for the cron. Each run reacts to the single most-liked fresh news item
(one post per run).

## Tuning the voice

The system prompt lives in `SPORTS_SYSTEM_PROMPT` near the top of `sports_pipe.py`. Edit there. Banned phrases live in `BANNED_SUBSTRINGS` and `BANNED_REGEX_PATTERNS` — add to those when you spot output that needs to be auto-rejected.

## Cost

- Anthropic API: ~$5-15/month at this volume (Haiku writer + Sonnet fact gate)
- Apify: ~$1/month
- Typefully: $0 (existing Enterprise account)
- GitHub Actions: $0 (free tier)
- Total: under $10/month
