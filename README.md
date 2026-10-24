# Latest-news
Welcome to my channel which is dedicated to providing free content to all users of my platform.

## Automated newsroom

This repository runs a fully automated news website. Every hour a GitHub Action:

1. **Collects** fresh items from news feeds (BBC, Al Jazeera, Guardian, NPR, The Verge, TechCrunch,
   Times of India, NDTV, The Hindu, Google News topic searches, Hacker News) and social media
   (Reddit, Mastodon, Bluesky).
2. **Groups** items that describe the same development, so ten posts about one event become one story.
3. **Writes** one original article per development with Claude. The article uses only facts from
   the sources, attributes every claim and labels social-media posts as unverified.
4. **Publishes** it to the website (GitHub Pages) and, optionally, to a WordPress site.
   Every article lists and links all of its sources.

A story is only written when at least `min_sources` independent sources report it, and at least
one of them is a news outlet, so a single viral post cannot become an article by itself. When a
published story gets 3 or more new sources, it is rewritten as an update instead of duplicated.

```
newsbot/collectors.py   fetch RSS, Google News, Hacker News, Reddit, Mastodon, Bluesky
newsbot/cluster.py      group items into developments (TF-IDF similarity)
newsbot/writer.py       write the article with Claude (falls back to a plain digest without a key)
newsbot/store.py        articles saved as JSON in data/articles/
newsbot/site.py         static site -> public/ (home, categories, articles, RSS, sitemap)
newsbot/wordpress.py    optional WordPress publishing
config.yaml             sources, topics, limits, site title
```

## Setup (one time)

1. **Add your Claude API key**: repository *Settings → Secrets and variables → Actions → New
   repository secret*, name `ANTHROPIC_API_KEY`. Without it the bot still runs but publishes
   simple source digests instead of written articles.
2. **Turn on the website**: *Settings → Pages → Build and deployment → Source: GitHub Actions*.
   The site will be at `https://<your-user>.github.io/Latest-news/`. Set `site.base_url` in
   `config.yaml` to that address.
3. **Merge to `main`.** GitHub only runs scheduled workflows from the default branch. After the
   merge you can also start a run by hand: *Actions → Newsroom → Run workflow*.

### Optional: publish to your WordPress site too

Create an Application Password in WordPress (*Users → Profile → Application Passwords*) and add
these repository secrets: `WP_URL` (e.g. `https://mynews.com`), `WP_USER`, `WP_APP_PASSWORD`.
Every new or updated article is then also posted to WordPress, with its category.

## Customising

Everything is in `config.yaml`: add or remove feeds, subreddits, hashtags and Google News topics,
change how many sources a story needs (`min_sources`), the per-run article limit (which controls
API cost) and the site title.

## Run locally

```bash
pip install -r requirements.txt
python -m newsbot run --dry-run   # collect + group only, shows which stories would be written
export ANTHROPIC_API_KEY=...      # optional
python -m newsbot run             # write articles and build the site into public/
python -m newsbot build           # rebuild the site from stored articles only
python -m pytest
```

## Notes

- X (Twitter), Instagram and Facebook are not included: their APIs require paid or approved
  access. Their news usually also appears on Reddit, Bluesky and Mastodon, which are covered.
- Articles are written from headlines and snippets and always link to the original reporting.
  Review the site regularly, especially early on, and tighten `min_sources` if needed.
