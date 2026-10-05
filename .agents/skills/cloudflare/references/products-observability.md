# Logs・analytics・診断

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Debug failures and trace application requests | Workers Logs and Traces | Investigate runtime errors and execution paths | [Observability](observability/README.md) |
| Process Worker execution events in code | Tail Workers | Build custom log or exception processing | [Tail Workers](tail-workers/README.md) |
| Export Worker logs to another system | Workers Logpush | Deliver logs to a supported external destination | [Logpush docs](https://developers.cloudflare.com/workers/observability/logs/logpush/index.md) |
| Measure custom application events | Workers Analytics Engine | Analyze high-cardinality event data written from Workers | [Analytics Engine](analytics-engine/README.md) |
| Measure website usage and visitor performance | Cloudflare Web Analytics | Add website analytics and real-user measurements | [Web Analytics](web-analytics/README.md) |
| Query metrics across Cloudflare products | GraphQL Analytics API | Retrieve product analytics programmatically | [GraphQL Analytics API](graphql-api/README.md) |
| Audit page speed and find loading bottlenecks | Web performance tools | Measure and improve the site's actual browser performance | `web-perf` skill; [Web Analytics](web-analytics/README.md) |
| Ask questions about an account or diagnose its configuration in the dashboard | Agent Lee | Use the dashboard's AI assistant; check current account eligibility | [Agent Lee docs](https://developers.cloudflare.com/agent-lee/index.md) |
