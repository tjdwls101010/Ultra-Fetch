# Getting Started

Follow this page start to finish and you'll have Ultra Fetch fetching, crawling, and mapping real
pages. For anyone setting this up in a new Claude Code project.

## 1. Prerequisites

- macOS or Linux, with `bash`.
- Python 3.12 available on the system `PATH` (used once, to bootstrap a dedicated virtualenv — it
  is not the interpreter that runs the CLI day to day).
- [`uv`](https://github.com/astral-sh/uv), optional — speeds up first-run provisioning if present;
  the launcher falls back to plain `venv` + `pip` otherwise.
- No accounts, no API keys. v1 is public-content only (see [Overview §6](Overview.md#6-non-goals-v1)).

## 2. Installation

Ultra Fetch is not a package — there's nothing to `pip install` or `npm install`. It's a directory
Claude Code recognizes as a skill:

```bash
cp -r .claude/skills/ultra-fetch /path/to/your-project/.claude/skills/
```

That's the whole install. Claude Code discovers skills under `.claude/skills/` automatically.

## 3. First run, end to end

Run the CLI directly once, so you can see exactly what it does before trusting it inside a Claude
Code session:

```bash
.claude/skills/ultra-fetch/scripts/ultra-fetch fetch https://example.com --output /tmp/example.md
```

The **first** invocation ever on a machine provisions a dedicated virtualenv at
`~/.cache/ultra-fetch/venv` and downloads both browser engines it depends on — a few hundred MB,
once. You'll see:

```
ultra-fetch: first run -- provisioning a dedicated environment.
ultra-fetch: this downloads several hundred MB of browser engines once, then never again.
```

Then the fetch itself runs and prints one summary line to stderr, something like:

```
fetched https://example.com via fast, 142 chars (clean), saved to /tmp/example.md
```

Every call after this first one skips provisioning and runs immediately.

## 4. Verify it worked

```bash
echo $?              # 0 = success
cat /tmp/example.md   # the actual page content, as markdown
```

Nothing useful was printed to stdout during the fetch itself — by design, so the result lives in a
file you control, not in whatever scrolled past in the terminal. See
[Concepts §4](Concepts.md#4-the-output-contract) for why.

## 5. Try `crawl` and `map` too

```bash
# A handful of pages under one site
.claude/skills/ultra-fetch/scripts/ultra-fetch crawl https://example.com --max-pages 5 --output /tmp/example-crawl/
cat /tmp/example-crawl/manifest.json

# What URLs exist on a domain, without fetching any of them
.claude/skills/ultra-fetch/scripts/ultra-fetch map example.com --output /tmp/example-urls.json
cat /tmp/example-urls.json
```

## 6. Using it from Claude Code (the normal path)

Once the skill directory is in place, you don't invoke any of the above by hand during real use.
Open Claude Code in the project and ask it to read, crawl, or map a page — `/ultra-fetch` fires on
its own whenever `WebFetch` would fall short, and Claude runs the CLI, reads the resulting file, and
reports back. Run `ultra-fetch catalog` (or ask Claude to) to see the full, always-current
command/flag contract for the version actually installed.

---
**Next:** [Concepts](Concepts.md) for the vocabulary used throughout the rest of the docs, or
[CLI Reference](CLI-Reference.md) for the full flag list. Back to the [index](README.md).
