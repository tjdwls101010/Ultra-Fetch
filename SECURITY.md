# Security Policy

## Supported versions

Ultra Fetch is a single-version, unreleased Claude Code skill (no tagged releases yet) — there is
no supported-versions matrix. Security fixes land on `main`.

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a security concern. Instead, email:

**chunghun1@naver.com**

Include:
- A description of the issue and its potential impact
- Steps to reproduce it (the exact `ultra-fetch` invocation, and the target if it's site-specific)
- The commit or version you tested against

## What's in scope

Ultra Fetch runs a stealth browser against arbitrary user-supplied URLs and writes their content to
disk. Reports of particular interest:
- Anything that lets a fetched page's content execute code, escape the browser sandbox, or write
  outside the intended `--output` path
- Credential or secret leakage (there are none by design in v1 — no auth, no API keys — so a report
  that one exists anywhere is a genuine bug)
- Dependency vulnerabilities in `scrapling` or `crawl4ai` that are exploitable through this CLI's
  usage of them

Being blocked by a target site's bot protection, or a page that fails to extract cleanly, is a bug
— not a security issue. Report those on the issue tracker instead.

## Response expectations

This is a solo-maintained project. There's no SLA, but reports will be acknowledged as soon as
they're seen and fixed before any public disclosure of the specifics. Please give a reasonable
window to land a fix before disclosing publicly.
