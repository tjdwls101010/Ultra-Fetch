# Ultra Fetch Wiki

The comprehensive documentation layer for Ultra Fetch — a Claude Code skill and CLI that fetches,
crawls, and maps web pages the built-in `WebFetch` can't reach. The [repo README](../../README.md)
is the front door; this wiki is where the depth lives.

## 1. Contents

| Page | What's in it |
|---|---|
| [Overview](Overview.md) | The problem, what this project does about it, where it sits among alternatives, who it's for, and what's deliberately out of scope. |
| [Getting Started](Getting-Started.md) | Prerequisites, installing the skill into a project, and a first `fetch`/`crawl`/`map` end to end. |
| [Architecture](Architecture.md) | The two-layer design, data-flow diagrams for each command, and the module map. |
| [Concepts](Concepts.md) | The vocabulary used everywhere else: access tiers, content refinement, crawl vs. map, the output contract, exit codes, the manifest. |
| [CLI Reference](CLI-Reference.md) | Every command, flag, default, and exit code, as implemented. |
| [Troubleshooting & Reading Results](Troubleshooting.md) | What to do when a result looks wrong — over-filtered, off-topic, a shallow crawl, a failing exit code. |
| [Design Decisions](Design-Decisions.md) | Why each default is what it is, argued against the alternative it beat. |
| [Validation History](Validation-History.md) | What real-site end-to-end testing actually found, across 15+ rounds. |
| [Development Guide](Development-Guide.md) | Working on the code itself: the dedicated venv, running tests, upgrading dependencies. |

## 2. Start here

New to this project? Read [Overview](Overview.md) first for what it is and why it exists, then
[Getting Started](Getting-Started.md) to actually run it.

Already using it and something looks off? Go straight to
[Troubleshooting & Reading Results](Troubleshooting.md).

Modifying the code? [Architecture](Architecture.md) → [Development Guide](Development-Guide.md).
