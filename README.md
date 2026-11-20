# inroad-lite

[![CI](https://github.com/alishair7071/inroad-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/alishair7071/inroad-lite/actions/workflows/ci.yml)

**Tell it the jobs you want. It finds companies hiring for them right now,
checks every opening is real, and ranks them by how well they fit you, with
the reason for each one.** It uses [Olostep](https://olostep.com) to search
the web and read company websites.

## What this project is

[Inroad](https://inroad-web.vercel.app/) is a platform that helps people find
companies worth applying to, research them, and reach out.

**This is not the full Inroad.** It is a smaller, open-source version that
keeps only the core: finding companies and matching them to a person.

- The full Inroad is several separate apps (a website, a backend, a data
  service), each in its own repository, with databases and background jobs.
- inroad-lite is **one repository**. Each of those apps becomes a **folder**
  with the same name and the same job, so the design is the same, just
  smaller. It runs from the command line or a simple web page, with no
  database.

> **This is not Inroad's private code.** inroad-lite is a separate, simplified
> project written to be shared openly, and published. A few small pieces, such as the matching rules and the country
> list, are adapted from Inroad. Inroad's private code, data, users, keys,
> servers and most of its logic are not included.

## How it works

You describe yourself in a short file: the roles you want, your skills, where
you live, and whether you want remote work or to relocate. inroad-lite then:

1. **Searches the web with Olostep** for open jobs matching your roles.
2. **Checks each job on the company's own job board**, so only real, still-open
   jobs are kept.
3. **Matches the jobs to you**: is it your kind of role, your level, and can
   you work it from where you live?
4. **Scores and ranks** the companies, and explains every score.
5. **Describes the top companies** by reading their homepage with Olostep.

### The parts

```mermaid
flowchart LR
    you(["You"])
    subgraph lite["inroad-lite"]
        web["<b>web</b><br/>where you start it<br/>and see the results"]
        api["<b>api</b><br/>matches jobs to you<br/>and ranks them"]
        sourcing["<b>sourcing</b><br/>finds and researches<br/>companies on the internet"]
    end
    olostep["<b>Olostep</b><br/>web search and<br/>website reading"]
    boards["<b>Company job boards</b><br/>Greenhouse, Lever, Ashby"]

    you --> web --> api --> sourcing
    sourcing --> olostep
    sourcing --> boards
```

- **web** is the front door. In the full Inroad it is the website; here it is
  a command you type, or a simple web page.
- **api** knows about you. It decides which jobs suit you and ranks them.
- **sourcing** knows about the outside world. It finds companies, researches
  them and checks their jobs. It never sees your full profile, only the roles, skills and
  place it needs to search.

### What happens when you run a search

```mermaid
flowchart TB
    a["1. Your profile<br/>roles, skills, location"]
    b["2. Search the web<br/>(Olostep search)"]
    c["3. Check each job on the<br/>company's own job board"]
    d["4. Keep the jobs that fit you<br/>and score them"]
    e["5. Describe the top companies<br/>(Olostep reads their homepage)"]
    f["6. Ranked list<br/>with reasons"]
    a --> b --> c --> d --> e --> f
```

1. **Your profile.** For example: Backend Engineer, Python and Docker, living
   in Lahore, open to remote work.
2. **Search.** sourcing turns that into a few web searches and runs them
   through Olostep at the same time. It searches only company job boards, so
   every result points to a real employer.
3. **Check.** A search result can be out of date, so sourcing opens each
   company's job board and keeps the company only if the job is still open.
4. **Fit and score.** api checks each job against you. A remote job open only
   in the US does not fit someone in Pakistan; a senior job does not fit
   someone with one year of experience. Jobs that fit get a score out of 100.
5. **Describe.** For the best few companies, sourcing finds their website and
   Olostep reads the homepage, giving a one-line description.
6. **Result.** You get the companies, best first. Every score shows why, and
   every company left out is counted with the reason.

A shortened real result, from a `--relaxed` run (with all checks on, the
strict rules kept 1 company for this profile, because most remote jobs are
open only in the US or Europe):

```text
40 results -> 25 job boards read -> 20 companies that fit you, best 10 shown (relaxed)

 1. YipitData   83 (strong)
    yipitdata.com  YipitData tracks trillions in live consumer and business spend ...
    Backend Engineer   97
      Role     Matches your target Backend Engineer
      Skills   Names Python, Docker, AWS, Kubernetes
      Level    Mid level, fits your 2 years
      Posted   23 days ago
```

Full examples are in [`examples/`](examples/).

### Research one company

You can also give it a single company's website:

```bash
uv run inroad-lite research yipitdata.com --profile profile.yaml
```

It follows the same steps as Inroad's company research:

```mermaid
flowchart TB
    a["1. Read the homepage<br/>and pick the pages worth reading<br/>(Olostep scrape)"]
    b["2. Read those pages<br/>about, careers, product...<br/>(Olostep scrape)"]
    c["3. Note what the site says<br/>each fact with its source page"]
    d["4. Find its job board<br/>and list the open roles"]
    e["5. Show the roles that fit you<br/>(with --profile)"]
    a --> b --> c --> d --> e
```

1. **Reads the homepage** with Olostep and picks the pages worth reading:
   about, careers, product, team, customers, news.
2. **Reads those pages** with Olostep (up to 4, one credit each).
3. **Notes what the site says**: when the company was founded, its size, its
   customers, funding, where it is based, its LinkedIn and GitHub. Each fact
   comes with the sentence and page it was found on.
4. **Finds its job board** and lists every open role.
5. With `--profile`, **shows which of those roles fit you**, scored the same
   way as a search.

A shortened real result:

```text
YipitData  (yipitdata.com)
YipitData is a fast-growing data and analytics company on a mission to give brands and ...

What the website says:
  Founded      Founded in 2013
               "2013Founded in New York City 650+Customers across brands and investors ..."
               source: https://yipitdata.com/about
  Team size    750+ people
               "We're 750+ people across the globe, focused on one thing ..."
               source: https://yipitdata.com/about
  Customers    650+ customers
               ...

Open roles: 40 on greenhouse: yipitdata
```

inroad-lite finds these facts with simple rules, not an AI model, so it
finds fewer, but never one the site does not plainly say.

## Where Olostep is used

Every call to Olostep goes through **one file**, so it is easy to see exactly
how Olostep is used. There are four kinds of call:

```mermaid
flowchart LR
    find["Finding companies"]
    site["Finding a company's website"]
    read["Describing a company"]
    research["Researching one company"]
    client["olostep.py<br/>the one file that<br/>talks to Olostep"]
    olostep["Olostep"]

    find -- "search" --> client
    site -- "search" --> client
    read -- "scrape" --> client
    research -- "scrape" --> client
    client --> olostep
```

| What it does | File to open |
|---|---|
| The only code that calls Olostep: search and scrape, with a time limit, a retry, and a running count of credits | [`sourcing/net/olostep.py`](src/inroad_lite/sourcing/net/olostep.py) |
| Writes the job searches sent to Olostep | [`sourcing/discovery/company_candidates.py`](src/inroad_lite/sourcing/discovery/company_candidates.py) |
| Runs those searches, several at once, to find companies | [`sourcing/services/company_discovery.py`](src/inroad_lite/sourcing/services/company_discovery.py) |
| Finds a company's website with a search, then reads its homepage with a scrape | [`sourcing/services/company_profile.py`](src/inroad_lite/sourcing/services/company_profile.py) |
| Researches one company: reads its homepage and its about, careers and other pages with scrapes | [`sourcing/services/company_research.py`](src/inroad_lite/sourcing/services/company_research.py) |
| Sets Olostep up with your key, the time limit, and a cache so repeat runs cost nothing | [`sourcing/api/dependencies.py`](src/inroad_lite/sourcing/api/dependencies.py) |

A full search costs about 20 to 40 Olostep credits (5 per search, 1 per page
read); researching one company about 5. Answers are saved for 6 hours, so
running the same thing again costs nothing.

## Try it

You need [uv](https://docs.astral.sh/uv/) and an Olostep API key.

```bash
git clone https://github.com/alishair7071/inroad-lite.git
cd inroad-lite
uv sync
cp .env.example .env                  # put your OLOSTEP_API_KEY in .env
uv run inroad-lite check              # confirms the key works
uv run inroad-lite search profile.example.yaml
```

Copy [`profile.example.yaml`](profile.example.yaml) to describe yourself.
Add `--relaxed` to skip the location and level checks.

For engineers: a detailed technical write-up is in
[docs/architecture.md](docs/architecture.md), and `uv run pytest` runs the
tests without a key.

## Use it in the browser

inroad-lite also has a simple web page with the same two features: find
companies, and research one company. Start it on your computer:

```bash
uv run uvicorn main:app --port 8010
```

Then open http://127.0.0.1:8010. Put `INROAD_LITE_ACCESS_CODE=` with a code
of your choice in `.env` first: every run spends Olostep credits, so the page
asks for that code and refuses to run without one. Runs are also limited per
hour (`INROAD_LITE_RUNS_PER_HOUR`, default 10).

The page is the **web** part, in
[`web/server.py`](src/inroad_lite/web/server.py) and
[`web/static/index.html`](src/inroad_lite/web/static/index.html). It calls the
same api code as the command line, so results are the same.

### Put it online with Vercel

1. Import this GitHub repository in Vercel. It finds `main.py` and runs it as
   a Python function; `vercel.json` lets a run take up to 5 minutes.
2. In the project's **Settings > Environment Variables**, add
   `OLOSTEP_API_KEY` and `INROAD_LITE_ACCESS_CODE`.
3. Deploy, open the address Vercel gives, and enter the access code.

On Vercel the 6-hour cache lasts only while a server instance is alive, so
repeat runs may spend credits again.

## How to test it

After the steps in **Try it**, run these one by one. Each says what you
should see.

1. **Check your Olostep key works.**
   ```bash
   uv run inroad-lite check
   ```
   You should see something like `Olostep key works: 12 results, 5 credits used.`

2. **Run a search with the example profile.**
   ```bash
   uv run inroad-lite search profile.example.yaml
   ```
   Takes under a minute the first time. You get a ranked list of companies,
   each with a score and the reasons, then a "Left out" list saying why the
   other companies were dropped, and the Olostep credits the run used.

3. **Run it with the checks relaxed.**
   ```bash
   uv run inroad-lite search profile.example.yaml --relaxed
   ```
   You should see more companies. Each one marked "location not checked" is
   a job you might not be able to work from your country.

4. **Run the same search again.**
   ```bash
   uv run inroad-lite search profile.example.yaml
   ```
   Same result, much faster, and the last line says `0 credits`: Olostep's
   answers were saved and reused.

5. **Search for yourself.** Copy `profile.example.yaml` to `profile.yaml`,
   change the roles, skills and location, and run:
   ```bash
   uv run inroad-lite search profile.yaml
   ```

6. **Save the result to a file**, to look at or share:
   ```bash
   uv run inroad-lite search profile.yaml --json results/me.json
   ```

7. **Research one company.**
   ```bash
   uv run inroad-lite research yipitdata.com --profile profile.example.yaml
   ```
   You get a short description, what the website says (each fact with its
   source page), the company's open roles, and which of them fit the profile.
   Try a company you know, too.

8. **Run the automated tests.** No key and no internet needed: they use a
   pretend Olostep and pretend job boards.
   ```bash
   uv run pytest
   ```
   Every test should pass in a few seconds.
