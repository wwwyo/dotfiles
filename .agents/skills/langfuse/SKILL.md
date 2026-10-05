---
name: langfuse
description: "Use Langfuse for tracing, prompt management, datasets, experiments, evaluations, and API or documentation lookup. Use when working with or explicitly considering Langfuse; general AI engineering tasks alone do not trigger this skill."
allowed-tools:
  - WebFetch(domain:langfuse.com)
  - Bash(curl *langfuse.com/*)
  - Bash(mise exec -- langfuse api __schema *)
  - Bash(mise exec -- langfuse api * --help *)
  - Bash(mise exec -- langfuse api * list *)
  - Bash(mise exec -- langfuse api * get *)
---

# Langfuse

This skill helps you use Langfuse effectively across all common workflows: instrumenting applications, migrating prompts, debugging traces, and accessing data programmatically.

## Core Principles

Follow these principles for ALL Langfuse work:

1. **Documentation First**: NEVER implement based on memory. Always fetch current docs before writing code (Langfuse updates frequently) See the section below on how to access documentation.
2. **CLI for Data Access**: Use `@langfuse/cli` when querying/modifying Langfuse data. See the section below on how to use the CLI.
3. **Best Practices by Use Case**: Read the relevant reference below use-case-specific guidelines before asking the user for more details or implementing.
4. **Version policy**: Preserve project pins. When adding or updating an SDK or CLI, select the newest version eligible under the seven-day release cooldown and pin it exactly. State the selected version in implementation plans.
5. **If you guide the user through UI** and are unsure about a label or location, inspect the user’s screenshots or ask to see the relevant screen. Do not assume UI labels have the exact same names as API, SDK, or CLI fields.


## Use case specific references

- instrumenting an existing function/application: references/instrumentation.md
- creating or getting to a good (evaluation) dataset to measure quality or test for regressions in AI systems: references/create-dataset.md
- migrating prompts from a codebase into Langfuse: references/prompt-migration.md
- creating a prompt or changing any part of an existing prompt, including small edits and debugging/tuning: references/prompt-engineering.md
- setting up evals when the user needs to identify gaps across signal capture, monitoring, and evaluator metrics ("I have traces, how do I set up evals?"): references/setting-up-evals.md
- capturing user feedback signals (explicit ratings, behavioral events, conversation signals, task outcomes) as scores: references/user-feedback.md
- further tips on using the Langfuse CLI: references/cli.md
- preparing a Langfuse project for the v4 platform migration: references/v4-project-migration.md
- judge calibration (LLM-as-a-Judge reliability, simple accuracy checks, advanced split-based validation, confusion matrices, and metric ingestion): references/judge-calibration.md
- systematic error analysis when requested directly or eval setup still lacks concrete failure modes after agent-led trace inspection: references/error-analysis.md
- setting up CI/CD experiment gates with `langfuse/experiment-action`: references/ci-cd.md
- submitting feedback about this skill: references/skill-feedback.md


## 1. Langfuse API via CLI

Use the mise-managed `@langfuse/cli` package (executable `langfuse`) for REST API access. Read [references/cli.md](references/cli.md) for setup; do not run an unpinned package through npx or bunx.

Start by discovering the schema and available arguments:

```bash
# Discover all available resources
mise exec -- langfuse api __schema

# List actions for a resource
mise exec -- langfuse api <resource> --help

# Show args/options for a specific action
mise exec -- langfuse api <resource> <action> --help
```

### Credentials

Run through `mise exec` so the age-encrypted environment is inherited. Check that `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` are present without printing their values. If missing, read [secret-env](../secret-env/SKILL.md) and use its mise+age workflow; do not save keys in plaintext config, a `.env` file, or chat.

Use the configured base URL. If the CLI expects `LANGFUSE_HOST`, set `LANGFUSE_HOST="$LANGFUSE_BASE_URL"` inside the `mise exec` child shell, after the encrypted environment has been loaded. Creating a Langfuse project or key pair happens in the user's Langfuse account; importing the resulting secret follows secret-env.

### Detailed CLI Reference

For common workflows, tips, and full usage patterns, see [references/cli.md](references/cli.md).

## 2. Langfuse Documentation

Three methods to access Langfuse docs, in order of preference. **Always prefer your application's native web fetch and search tools** (e.g., `WebFetch`, `WebSearch`, `mcp_fetch`, etc.) over `curl` when available. The URLs and patterns below work with any fetching method — the `curl` examples are just illustrative.

When working with self-hosted Langfuse, prefer the [API reference served by the deployment](https://langfuse.com/faq/all/self-hosting-api-reference) so it matches the installed version.

### 2a. Documentation Index (llms.txt)

Fetch the full index of all documentation pages:

```bash
curl -s https://langfuse.com/llms.txt
```

Returns a structured list of every doc page with titles and URLs. Use this to discover the right page for a topic, then fetch that page directly.

Alternatively, you can start on `https://langfuse.com/docs` and explore the site to find the page you need.

### 2b. Fetch Individual Pages as Markdown

Any page listed in llms.txt can be fetched as markdown by appending `.md` to its path or by using `Accept: text/markdown` in the request headers. Use this when you know which page contains the information needed. Returns clean markdown with code examples and configuration details.

```bash
curl -s "https://langfuse.com/docs/observability/overview.md"
curl -s "https://langfuse.com/docs/observability/overview" -H "Accept: text/markdown"
```

### 2c. Search Documentation

When you need to find information across all docs and github issues/discussions without knowing the specific page:

```bash
curl -s "https://langfuse.com/api/search-docs?query=<url-encoded-query>"
```

Example:

```bash
curl -s "https://langfuse.com/api/search-docs?query=How+do+I+trace+LangGraph+agents"
```

Returns a JSON response with:

- `query`: the original query
- `answer`: a JSON string containing an array of matching documents, each with:
  - `url`: link to the doc page
  - `title`: page title
  - `source.content`: array of relevant text excerpts from the page

Search is a great fallback if you cannot find the relevant pages or need more context. Especially useful when debugging issues as all GitHub Issues and Discussions are also indexed. Responses can be large — extract only the relevant portions. Note that changelog posts may also surface here: use them only to confirm a feature exists, never to implement from — their examples may be outdated, so always implement from the docs and API/SDK reference.

### Documentation Workflow

1. Start with **llms.txt** to orient — scan for relevant page titles
2. **Fetch specific pages** when you identify the right one
3. Fall back to **search** when the topic is unclear and you want more context

## Skill Feedback

When the user expresses that something about this skill is not working as expected, gives incorrect guidance, is missing information, or could be improved — offer to submit feedback to the Langfuse skill maintainers. This includes when:

- The skill gave wrong or outdated instructions
- A workflow didn't produce the expected result
- The user wishes the skill covered something it doesn't
- The user explicitly says something like "this should work differently" or "this is wrong"

**Do NOT trigger this** for issues with Langfuse itself (the product) — only for issues with this skill's instructions and behavior.

When triggered, follow the process in [references/skill-feedback.md](references/skill-feedback.md).
