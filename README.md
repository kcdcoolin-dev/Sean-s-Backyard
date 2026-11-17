# Sean's Backyard

The site for every league, game and event Sean makes his friends play.

## How it works

- Everything you can edit lives in `content/` as plain text files.
- `build.py` turns those files into the web pages, using the layouts in `templates/` and the look in `static/style.css`.
- Each time a change is saved to GitHub, the site rebuilds and republishes itself (takes about a minute).

| Folder or file | What it holds |
|---|---|
| `content/leagues/` | One file per league or event |
| `content/seasons/` | One file per season: champion, standings or cast, recap |
| `content/people/` | One file per person |
| `content/posts/` | Blog posts |
| `content/records.yml` | Records you add by hand (championships are counted automatically) |
| `content/settings.yml` | Site name, home page headline and tagline, footer |
| `media/` | Images uploaded through the admin screen |

## One-time setup

1. **Create the repository.** On github.com, create a new *public* repository and put these files in it. Make sure the hidden items come along: the `.github` folder and the `.pages.yml` file.
2. **Turn on publishing.** In the repository, go to Settings, then Pages, and set the source to "GitHub Actions". The site address appears there after the first build.
3. **Connect the admin screen.** Go to https://app.pagescms.org, sign in with GitHub, and install its GitHub App on this repository. Open the repository there to start editing.

## Day to day

- **Write a post:** admin screen, Blog posts, add an entry.
- **Start a season:** admin screen, Seasons and results, add an entry and pick the league.
- **Enter results:** open the season and fill in the standings (fantasy) or cast (games). List teams in finishing order.
- **Add a person first** (People) so they can be picked as a manager, player or champion.

## Building it on your own computer (optional)

```
pip install -r requirements.txt
python build.py
```

The pages land in `_site/`.
