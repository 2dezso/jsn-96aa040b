# JSN FPL

Jim Sport News: how the six of us really did each gameweek. The product doc stays private (not in this repo).

## Layout

| Folder | What it is |
|---|---|
| `pipeline/build.py` | Pulls the FPL API for the six managers, computes every metric, writes `data/site.json`. Raw responses are cached in `data/raw`. |
| `site/src` | The real site: `index.html` (the app) and `stories.html`, plus shared pieces in `lib/`. |
| `site/build.py` | Inlines the data into the pages and writes `site/public`. Refuses to build if the pipeline's checks against the league table failed. |
| `prototypes/` | Design sandbox. Not published. |
| `.github/workflows/publish.yml` | Every morning at 06:00 UTC, on every push to `main`, and by hand: pull data, build, deploy to GitHub Pages. |

## Run it locally

```
python pipeline/build.py
python site/build.py
```

Open `site/public/index.html` in a browser.

Moving a prototype change into the site: edit `site/src` directly. The prototypes are only for trying ideas.

## Publish (one-time setup)

1. Create an empty GitHub repo, for example `jsn-fpl`. Pages on a private repo needs a paid plan, so on the free plan it must be public. That's acceptable: the data is public FPL data, the site uses nicknames and team names only, and every page carries `noindex` plus a `robots.txt` that blocks crawlers.
2. From this folder:
   ```
   git init -b main
   git add .
   git commit -m "JSN site and publish workflow"
   git remote add origin https://github.com/<you>/jsn-fpl.git
   git push -u origin main
   ```
3. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. **Actions → Publish → Run workflow** (or just wait for the push run). The site appears at `https://<you>.github.io/jsn-fpl/`.
5. Share the link in the group chat.

After that it refreshes itself every morning. To force a refresh (say, right after a gameweek's bonus points land), run the workflow by hand.

## Still to do before calling it v1

- **Who opens it:** PRD success metric needs privacy-friendly analytics and per-person links (`?u=jim`). GoatCounter is free and needs one script tag.
- **Custom or less guessable URL:** a repo name nobody would guess, or a custom domain.
- **Shorter refresh lag:** if 06:00 UTC is too slow after a Monday night game, add a second cron time.
