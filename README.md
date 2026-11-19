# inroad-lite

[![CI](https://github.com/alishair7071/inroad-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/alishair7071/inroad-lite/actions/workflows/ci.yml)

Find companies that are hiring for your roles right now, check each opening
on the company's own job board, and rank them by how well they fit you, with
the reason for every point.

It is a small, standalone version of the company discovery and matching in
[Inroad](https://inroad-web.vercel.app/), built on
[Olostep](https://olostep.com) search and scrape plus the public Greenhouse,
Lever and Ashby job board APIs. The folders mirror Inroad's services
(`web`, `api`, `sourcing`); [docs/architecture.md](docs/architecture.md)
shows how.

```text
profile.yaml ─► Olostep search ─► companies from job-board links ─► each board read:
                (4 at once)                                         is the posting open?
             ─► does it fit you? (role, level, location) ─► score 0-100 with reasons
             ─► Olostep scrape of the top companies' homepages ─► ranked list
```

## What a run looks like

Real output, lightly trimmed, for [`profile.example.yaml`](profile.example.yaml)
(Backend or DevOps Engineer, 2 years, in Lahore, open to remote work or
relocating to Europe or Canada):

```text
$ uv run inroad-lite search profile.example.yaml
Searched 4 queries.
40 results -> 25 job boards read -> 1 company that fits you

 1. Schuberg Philis   74 (good)   [greenhouse: schubergphilis]
    schubergphilis.com  Mission-critical IT has always been at the heart of our work. ...
    Windows DevOps Automation Engineer   85
      Role     Matches your target DevOps Engineer
      Skills   Names Python, Docker, Kubernetes
      Level    Mid level, fits your 2 years
      Posted   98 days ago
      Location Schiphol-Rijk, North Holland, Netherlands, with relocation support
      https://schubergphilis.com/careers/7809600003?greenhouse=1&gh_jid=7809600003

Left out:
   19  not open where you can work
   11  not the role searched for
    3  posting already closed
    1  not a Greenhouse, Lever or Ashby link
    1  job board could not be read
    1  wrong level for your experience
```

Most remote roles are open only in the US or Europe, so for someone in
Pakistan the strict rules keep one company out of 25, and say why for every
one they drop. `--relaxed` checks the role only:

```text
$ uv run inroad-lite search profile.example.yaml --relaxed
40 results -> 25 job boards read -> 10 companies that fit you (relaxed: location and level not checked)

 1. YipitData   83 (strong)   [greenhouse: yipitdata]
    yipitdata.com  YipitData tracks trillions in live consumer and business spend, so you can ...
    Backend Engineer   97
      Role     Matches your target Backend Engineer
      Skills   Names Python, Docker, AWS, Kubernetes
      Level    Mid level, fits your 2 years
      Posted   23 days ago
      Location India Remote (location not checked)
 ...
```

Full output and JSON for both runs are in [`examples/`](examples/). Job
boards are read live on every run, so counts move a little from one run to
the next as postings open and close.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and an [Olostep](https://olostep.com) API key.

```bash
git clone https://github.com/alishair7071/inroad-lite.git
cd inroad-lite
uv sync
cp .env.example .env                 # then put your OLOSTEP_API_KEY in .env
uv run inroad-lite check             # one search: confirms the key works (5 credits)
cp profile.example.yaml profile.yaml # then edit it to describe yourself
uv run inroad-lite search profile.yaml
```

### The profile

```yaml
roles: [Backend Engineer, DevOps Engineer]   # up to 4
skills: [Python, Docker, AWS, Kubernetes]    # the first 6 go into searches
location: Lahore, Pakistan                   # "City, Country"
work_preference: [remote, relocation]        # remote, onsite, hybrid, relocation
relocation_places: [Europe, Canada]          # optional
years_experience: 2                          # optional, used for level
```

### Options

| Option | What it does |
|---|---|
| `--relaxed` | Check the role only, not location or level. Matches are labelled "location not checked" |
| `--about N` | Describe the top N companies from their homepage (default 3, `0` to skip) |
| `--fresh` | Ask Olostep again instead of using the 6-hour cache |
| `--json FILE` | Also save the result as JSON |

## How it works

**Sourcing finds and proves (Stage A).** It turns the profile into up to four
searches restricted to job-board sites, for example
`"Backend Engineer" Python remote (worldwide OR anywhere OR global OR Pakistan) (site:boards.greenhouse.io OR ...)`,
and runs them through Olostep at the same time. A Greenhouse, Lever or Ashby
link names its employer in the URL, so each result becomes a company without
guessing. A search result is only a lead: sourcing then reads that company's
board through its public API, once per board, and keeps the company only if
the posting is still open.

**Api decides what fits you (Stage B).** Inroad's rules: is the role open
where you can work (a "Remote (US)" role is not open to Pakistan), is it
your level, is it your kind of role (a "Rust Engineer" posting is not a
Python backend role). The roles that fit get a 0-100 score from role (35),
skills named (40), level (10) and how recent (15), with every part shown.

**The best few get an "about".** Their website comes from a job link on the
company's own site when there is one (free), otherwise from one Olostep
search checked against the company name. Then Olostep scrapes the homepage
and the first paragraph that describes the company is kept.

Sourcing never sees the full profile: only roles, a few skills, the place
and work modes cross to it, as in Inroad. A test checks the boundaries
between `web`, `api` and `sourcing` on every run. More detail, with
diagrams: [docs/architecture.md](docs/architecture.md).

## Notes on using Olostep

What I measured while building this (a handful of runs, not a benchmark):

- **`site:` searches are slow, plain ones are not.** One search with four
  `site:` filters took 43.7 s on 2026-11-19; a plain query took 4.3 s.
  The next day four filtered searches running at once finished in about
  15 s. With Inroad's original 30 s timeout, most filtered searches were cut
  off that first evening and every company scan failed, so the default here
  is 60 s (`OLOSTEP_TIMEOUT_SECONDS`), with one retry.
- **Run searches at the same time.** They are independent, so four at once
  cost the time of the slowest one, not the sum.
- **Every response says what it cost.** `credits_consumed` came back on each
  call: 5 per search and 1 per scrape in these runs. inroad-lite adds them up
  and prints the total, so you always see what a run spent.
- **Cache what you can.** Answers are kept for 6 hours, so running the same
  profile again costs nothing. A fresh strict run cost about 21 credits
  (4 searches, 1 scrape); a fresh `--relaxed` run with three "about" lines
  about 38.
- **`json_content` is a JSON string inside the JSON response**, so search
  results are parsed twice (`olostep.py` shows how).
- **A scrape can come back in another language.** One company's homepage
  arrived in Russian, probably localised by where the request came from.
  The summary step skips paragraphs that are mostly another script and
  leaves the "about" blank rather than show the wrong thing.

Job boards had their own surprises: Greenhouse's job list with descriptions
was 3.9 MB for one company (175 KB without, so descriptions are fetched per
posting), and Ashby sends every posting with its full description (4 to 14 MB
for larger companies).

## Project layout

```text
src/inroad_lite/
  web/cli.py                       the command line (plays inroad-web)
  api/                             plays inroad-api
    routers/                       entry points web calls
    schemas/                       profile, results
    services/match_discovery.py    Stage B: fit, score, rank
    services/match_fit.py          role, level and location rules
    services/match_score.py        0-100 score with reasons
    services/sourcing_client.py    the only way api reaches sourcing
  sourcing/                        plays inroad-sourcing
    api/                           entry points api calls
    schemas/                       the contract api sees
    services/company_discovery.py  Stage A: search, merge, prove
    services/candidate_proof.py    read each board, is the posting open
    services/company_profile.py    website and "about" line
    discovery/                     queries, link reading, visa statements (no network)
    ats/                           Greenhouse, Lever, Ashby readers (no network)
    net/olostep.py                 the only code that calls Olostep
    net/fetcher.py                 the only code that calls job boards
  core/                            settings, cache, country table
tests/                             mirrors src; scripted Olostep and job boards
```

## Development

```bash
uv run pytest                                      # 114 tests, no key or network needed
uv run ruff check . && uv run ruff format --check .
uv run mypy                                        # strict
```

CI runs all of it on Python 3.11 and 3.12.

## Limits

- Three job boards (Greenhouse, Lever, Ashby). Inroad reads eight.
- Location and level come from what a posting states; a posting that names
  no place for a remote role is not counted as open to you.
- The "about" line is the first suitable paragraph of a homepage, not a
  summary written by a model.
- Searches depend on what Olostep's search returns that day.

## License

MIT. Built from Inroad's code (MIT, © Abdul Moiz and Inroad contributors);
see [LICENSE](LICENSE).
