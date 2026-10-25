# Logs・analytics・診断

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Debug failures and trace application requests | Workers Logs and Traces | Investigate runtime errors and execution paths | [Observability](observability/README.md) |
| Process Worker execution events in code | Tail Workers | Build custom log or exception processing | [Tail Workers](tail-workers/README.md) |
| Profile CPU usage or memory allocations in deployed Workers or Durable Objects | Workers profiling | Investigate CPU and memory issues in production | `workers-profiling` skill |
| Export Worker logs to another system | Workers Logpush | Deliver logs to a supported external destination | [Logpush docs](https://developers.cloudflare.com/workers/observability/logs/logpush/index.md) |
| Measure custom application events | Workers Analytics Engine | Analyze high-cardinality event data written from Workers | [Analytics Engine](https://developers.cloudflare.com/analytics/analytics-engine/index.md) |
| Measure website usage and visitor performance | Cloudflare Web Analytics | Add website analytics and real-user measurements | [Web Analytics](https://developers.cloudflare.com/web-analytics/index.md) |
| Query metrics across Cloudflare products | GraphQL Analytics API | Retrieve product analytics programmatically | [GraphQL Analytics API](https://developers.cloudflare.com/analytics/graphql-api/index.md) |
| Audit page speed and find loading bottlenecks | Web performance tools | Measure and improve the site's actual browser performance | `web-perf` skill; [Web Analytics](https://developers.cloudflare.com/web-analytics/index.md) |
| Ask questions about an account or diagnose its configuration in the dashboard | Agent Lee | Use the dashboard's AI assistant; check current account eligibility | [Agent Lee docs](https://developers.cloudflare.com/agent-lee/index.md) |
