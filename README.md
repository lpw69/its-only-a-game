# It's Only a Game

Automated content engine for [@ItsOnlyAGamee](https://www.threads.com/@ItsOnlyAGamee) on Threads.

Pulls breaking sports news from Fabrizio Romano, David Ornstein, BBC Sport and Sky Sports News every few hours, runs each item through a Paddy Power / Aldi-flavoured prompt, and pushes the resulting one-liner takes to Typefully as drafts ready to publish or schedule.

## Architecture

```
Apify (X scraper) → Claude Haiku (voice) → style validator → Claude Sonnet (fact gate) → Typefully → Threads
```

Single Python script, single GitHub Actions workflow.

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
