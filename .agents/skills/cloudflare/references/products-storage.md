# 共有状態・DB・files・cache

Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Coordinate chat rooms, games, collaborative documents, or bookings | Durable Objects | Operations need shared state and coordination per room, document, or entity | `durable-objects` skill; [Durable Objects docs](https://developers.cloudflare.com/durable-objects/index.md) |
| Store and recover state inside a Durable Object | Durable Object storage | Choose storage APIs, transactions, and recovery for coordinated per-entity data | [DO storage](do-storage/README.md) |
| Store application records and query them with SQL | D1 | Use a managed relational database; use Durable Objects when per-entity coordination is central | [D1](d1/README.md) |
| Connect to an existing PostgreSQL or MySQL database | Hyperdrive | Keep the existing database and optimize connections from Workers | [Hyperdrive](hyperdrive/README.md) |
| Distribute configuration or other key-value data | KV | Read-heavy key-value access fits the workload's consistency requirements | [KV](kv/README.md) |
| Store uploads, downloads, or large objects | R2 | Store files by object key; pair with D1 when searchable metadata needs SQL | [R2](r2/README.md) |
| Store versioned file trees, agent checkpoints, or repositories | Artifacts | Files need versioning and Git-compatible access; [open beta since 2026-10-01](https://developers.cloudflare.com/changelog/post/2026-10-01-artifacts-open-beta/), available on the Workers Paid plan | [Artifacts](artifacts/README.md) |
| Ingest event streams into R2 | Basin Pipelines | Transform and deliver streaming records into R2 | `basin` skill; [Basin Pipelines](https://developers.cloudflare.com/basin-pipelines/index.md) |
| Manage Iceberg tables in R2 | Basin Catalog | Organize tables for analytics and compatible query engines | `basin` skill; [Basin Catalog](https://developers.cloudflare.com/basin-catalog/index.md) |
| Query Iceberg tables with SQL | Basin SQL | Analyze tables in Basin Catalog | `basin` skill; [Basin SQL](https://developers.cloudflare.com/basin-sql/index.md) |
| Keep a durable event log with independent readers | K2 Streams | Produce records from Workers or HTTP, then consume with subscriptions | `k2` skill; [K2 docs](https://developers.cloudflare.com/k2/index.md) |
| Cache application responses | Workers Cache | Default for application caching; check the patterns and limitations before choosing alternatives | [Workers Cache](https://developers.cloudflare.com/workers/cache/index.md); see [caching guidance](../SKILL.md#caching) |
| Accelerate an existing website and control cached content | Cache/CDN | Configure caching for a proxied origin using Cache Rules, expiration settings, and purging | [Cache/CDN docs](https://developers.cloudflare.com/cache/index.md) |
| Keep origin content in a persistent cache | Cache Reserve | Reduce origin fetches with persistent CDN cache storage | [Cache Reserve](cache-reserve/README.md) |
