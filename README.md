# It's Only a Game

Automated content engine for [@ItsOnlyAGamee](https://www.threads.com/@ItsOnlyAGamee) on Threads.

Pulls breaking sports news from Fabrizio Romano, David Ornstein, BBC Sport and Sky Sports News every few hours, runs each item through a Paddy Power / Aldi-flavoured prompt, and pushes the resulting one-liner takes to Typefully as drafts ready to publish or schedule.

## Architecture

```
Apify (X scraper) → Claude Haiku (voice + validator) → Typefully (draft) → Threads
```

Single Python script, single GitHub Actions workflow, runs four times daily.

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

Or wait for the cron. Each run aims for ~6 drafts.

## Tuning the voice

The system prompt lives in `SPORTS_SYSTEM_PROMPT` near the top of `sports_pipe.py`. Edit there. Banned phrases live in `BANNED_SUBSTRINGS` and `BANNED_REGEX_PATTERNS` — add to those when you spot output that needs to be auto-rejected.

## Cost

- Anthropic API: ~$5/month at this volume
- Apify: ~$1/month
- Typefully: $0 (existing Enterprise account)
- GitHub Actions: $0 (free tier)
- Total: under $10/month
