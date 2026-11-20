# inroad-lite architecture

How inroad-lite is put together: the three parts, what each one owns, how a
search moves through them, and how it compares with a full system like
[Inroad](https://inroad-web.vercel.app/).

## 1. The parts

In a full system these would be separate services talking over HTTP. Here
each is a package under `src/inroad_lite/`, with its own layers and clear
rules about who may call whom.

| Part | Plays the role of | What it is | Owns |
|---|---|---|---|
| `web` | the website | The command line | Reading the profile file and printing results. Talks to `api`, nothing else |
| `api` | the backend | Routers, services, schemas | The person: their profile, whether a posting fits them (Stage B), the score and its reasons |
| `sourcing` | the data service | Entry points, services, board readers, network layer | Everything that reads the outside world: Olostep search and scrape, public job boards. Holds no user data |
| `core` | shared helpers | Settings, cache, country table | Shared helpers, no feature logic |

Two rules hold the split together:

- **Sourcing never sees the person.** It receives roles, at most six skill
  terms, a city and country, and work modes. Never years of experience, the
  full profile, or anything else about who is asking.
- **Only one door between parts.** `web` calls `api`'s routers;
  `api` reaches sourcing only through `api/services/sourcing_client.py` and
  sourcing's published schemas; only `sourcing/net/` opens a connection.

`tests/test_architecture.py` reads every module's imports and fails the
build if any of these rules is broken.

## 2. Architecture diagram

```mermaid
flowchart LR
    user(["Job seeker<br/>(terminal)"])

    subgraph web["web (plays inroad-web)"]
        cli["cli.py<br/>profile.yaml in, ranked list out"]
    end

    subgraph api["api (plays inroad-api)"]
        routers["routers<br/>match, health"]
        services["services<br/>match_discovery: Stage B<br/>match_fit, match_score"]
        sclient["sourcing_client<br/>the only door to sourcing"]
    end

    subgraph src["sourcing (plays inroad-sourcing)"]
        entry["api<br/>company_discovery, company_profile"]
        disc["services<br/>company_discovery: Stage A<br/>candidate_proof, company_profile"]
        pure["discovery + ats<br/>queries, link reading, board readers<br/>(no network)"]
        net["net<br/>olostep.py, fetcher.py"]
    end

    subgraph ext["External"]
        olostep["Olostep<br/>/v1/searches, /v1/scrapes"]
        boards["Public job board APIs<br/>Greenhouse, Lever, Ashby"]
    end

    cache[(".cache/<br/>Olostep answers, 6 h")]

    user --> cli --> routers --> services --> sclient --> entry --> disc
    disc --> pure
    disc --> net
    net --> olostep
    net --> boards
    net <--> cache
```

## 3. Who owns what

| Thing | Owner | Why there |
|---|---|---|
| The profile (roles, skills, place, years, preferences) | `api` | It is about a person |
| The search request | built by `api`, read by `sourcing` | `api` decides what little crosses |
| Search queries, reading companies from links | `sourcing/discovery` | Public data, no person needed |
| Reading job boards, proving a posting is open | `sourcing/services/candidate_proof.py` + `sourcing/ats` | Public data |
| Visa and relocation statements in a posting | `sourcing/discovery/visa_statement.py` | A fact about the posting, the same for everyone |
| Does this posting fit this person | `api/services/match_fit.py` | Personal: depends on where they live and what they want |
| The 0-100 score and its reasons | `api/services/match_score.py` | Personal |
| A company's website and "about" line | `sourcing/services/company_profile.py` | Public data |

## 4. Find companies, end to end

```mermaid
sequenceDiagram
    autonumber
    participant C as web (cli)
    participant A as api
    participant S as sourcing
    participant O as Olostep
    participant J as Job boards

    C->>A: find_companies(profile, relaxed, about)
    A->>A: build the request (roles, 6 skills, place, modes)
    A->>S: discover(request) via sourcing_client
    par up to 4 searches at once
        S->>O: POST /v1/searches (ATS site: filter, cached 6 h)
    end
    S->>S: read company and posting from each link, merge by board
    par each board once, shared by its candidates
        S->>J: GET the board's job list (public API)
    end
    S->>S: keep open postings for the roles, read visa / relocation
    S-->>A: proven companies, reject counts, Olostep usage
    A->>A: Stage B: fit each posting, score the fitting ones, rank companies
    par top N companies
        A->>S: profile(name, posting links)
        S->>O: POST /v1/searches "Name" official website (only if no link names the site)
        S->>O: POST /v1/scrapes homepage as markdown
        S-->>A: website and one-paragraph about
    end
    A-->>C: ranked companies, reasons, left-out counts, credits spent
```

Every left-out company is counted with a reason ("posting already closed",
"not open where you can work"), so a short list still explains itself.

## 5. How sourcing works (Stage A)

1. **Queries** (`discovery/company_candidates.py`). One query per role and
   work mode, up to four, each restricted to job-board sites:
   `"Backend Engineer" Python remote (worldwide OR anywhere OR global OR Pakistan) (site:boards.greenhouse.io OR ...)`.
   Postings on these boards name their employer in the URL, so a hit becomes
   a company without guessing. The wording was chosen by testing searches
   live.
2. **Candidates.** Each hit is read for its board (`greenhouse: gitlab`),
   posting id and role title. Aggregator boards, other roles and other sites
   are rejected with a reason. Hits on the same board are merged.
3. **Proof** (`services/candidate_proof.py`). A hit is a lead, not proof.
   Each board's public job list is read once and shared by every candidate
   on it. A posting found there is kept with its real title, location,
   remote or onsite, and description. A posting missing from a complete
   list is closed; from a partial one, unknown. A board that does not answer
   in 25 seconds is left out.
4. **Board readers** (`ats/greenhouse.py`, `lever.py`, `ashby.py`). They
   only build URLs and read answers into one `Job` shape; the fetch happens
   in `net/fetcher.py` (https only, only the host the reader names, no
   redirects, 20 s, 25 MB).

## 6. How api matches (Stage B)

`match_fit.py`, based on Inroad's matching rules:

- **Location.** Onsite or hybrid: the posting is in your country. Remote:
  open to your country by name, region ("APAC") or "worldwide"; "Remote
  (US)" is not. Relocation: in one of your chosen places, with visa
  sponsorship or relocation support stated, and not ruled out.
- **Level.** Staff needs 7+ years, senior 3+, junior under 3.
- **Role.** The title's family (backend, devops, design, sales
  engineering...) must be one you target; a title naming a stack you do not
  list ("Rust Engineer" for a Python profile) or a management role is a
  different job.

`match_score.py`, based on Inroad's scoring: role 35, skills 40, level 10,
freshness 15. A part that cannot be checked counts as half, so a posting
that says less does not outscore one that says more. A company ranks by its
best role and how many of its roles fit.

`--relaxed` keeps the role rules and drops location and level, and labels
every such match "location not checked".

### Researching one company

`inroad-lite research <website>` goes through the same boundaries:

1. `api/routers/research.py` → `api/services/company_research.py` →
   `sourcing_client.research`. The website is checked first
   (`research_target`): no IP addresses, ports, credentials or private names.
2. `sourcing/services/company_research.py` scrapes the homepage, picks up to
   four of the site's own pages by kind (`discovery/website_pages.py`: about,
   careers, product, team, customers, news) and scrapes them at once.
3. `discovery/company_facts.py` reads facts by phrase rules (founded, size,
   customers, funding, headquarters, social links), each kept with its
   sentence and page. Rules find less than a language model would, but
   never misread.
4. The job board comes from a link on the home or careers page
   (`discovery/board_links.py`). Pages that load their board in the browser
   show none, so a board named after the site is tried, and kept only when
   its own data shows it is this company (Greenhouse's company name, or job
   descriptions naming the site).
5. With a profile, api runs Stage B on the open roles: same rules, same
   score. A role whose text was not read (Greenhouse listings carry none)
   counts its skills as unknown, not missing.

## 7. Boundaries

```mermaid
flowchart LR
    W["web"] -- "routers + schemas only" --> A["api"]
    A -- "sourcing_client + sourcing schemas;<br/>roles, skills, place, modes only" --> S["sourcing"]
    S -- "net/olostep.py: https, no redirects,<br/>no proxies, 60 s, 1 retry, cache" --> O["Olostep"]
    S -- "net/fetcher.py: https, named host only,<br/>no redirects, 20 s, 25 MB" --> J["Job boards"]
```

- The Olostep key is read from the environment and never logged or put in
  an error message.
- Tests blank the key and use a scripted Olostep and scripted job boards
  (`httpx.MockTransport`), so a missing fake fails instead of spending
  credits.

## 8. What is kept simple

| A full system would have | inroad-lite has |
|---|---|
| Separate services calling each other over the network | Packages calling each other through one client function each; `sourcing_client.py` is the one file to change to make sourcing a separate service |
| Databases and background workers | None. Results are printed and optionally saved as JSON |
| A web app | A command line |
| More job boards | Greenhouse, Lever, Ashby |
| More ways to prove which website a company owns | The board's own data names the company; the website for the "about" line is checked against the name |
| Stricter network safety checks | Fixed public job-board hosts only, no redirects |
| More signals about the person | Role, level, location and the skills a posting names |
| Deeper research of a company's site | Up to four pages read through Olostep scrapes; facts by phrase rules, with evidence |

## 9. Configuration

| Setting | Default | Effect |
|---|---|---|
| `OLOSTEP_API_KEY` | none | Required for `check` and `search` |
| `OLOSTEP_TIMEOUT_SECONDS` | 60 | Wait per Olostep call (job-board searches can take 45 s) |
| `OLOSTEP_BASE_URL` | `https://api.olostep.com/v1` | |
| `INROAD_LITE_CACHE_DIR` | `.cache` | Olostep answers are reused for 6 hours |
| `--fresh` | off | Ask Olostep again instead of using the cache |
| `--relaxed` | off | Check the role only, not location or level |
| `--about N` | 3 | Describe the top N companies from their homepage; 0 to skip |

## 10. Running and testing it

```bash
uv run pytest      # no key, no network
uv run ruff check . && uv run ruff format --check .
uv run mypy        # strict
```

CI runs the same on Python 3.11 and 3.12 (`.github/workflows/ci.yml`).
