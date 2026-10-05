# websites・API・実行環境

Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Start a Worker or framework project | C3 | Scaffold a project using the appropriate framework template | [C3](c3/README.md); `wrangler` skill |
| Build or deploy a Next.js app on Cloudflare | vinext + Workers | Use vinext rather than OpenNext for new projects | nextjs-on-cloudflare skill; [Next.js docs](https://developers.cloudflare.com/workers/framework-guides/web-apps/nextjs/index.md) |
| Host a new static site, SPA, or full-stack app | Workers + Workers Static Assets | Serve site files and add server-side logic where needed | [Static Assets](static-assets/README.md); `workers-best-practices` skill |
| Build an API or handle webhooks | Workers | Run request handlers with access to Cloudflare services | `workers-best-practices` skill; [Workers docs](https://developers.cloudflare.com/workers/index.md) |
| Control team, CI, or service-account access to Developer Platform resources | Roles, scopes, and permission policies | Choose the least-privilege role and a scope supported for the member, User Group, or API token | [Roles and permissions](https://developers.cloudflare.com/workers/authorization/index.md); `wrangler` skill for CLI access |
| Maintain an existing Pages deployment | Pages + Pages Functions | Update an existing site or its server endpoints; use Workers for new projects | [Pages](pages/README.md); [Pages Functions](pages-functions/README.md) |
| Move a Pages project to Workers | Workers + Workers Static Assets | The task calls for migrating the hosting platform | [Pages migration guide](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/index.md) |
| Let customers deploy code on your platform | Workers for Platforms | Run and manage customer Workers with per-customer controls | [Workers for Platforms](workers-for-platforms/README.md) |
| Let customers use their own domains with your app | Cloudflare for SaaS | Manage custom hostnames, TLS certificates, and origin routing; check hostname validation and apex-domain plan requirements. Combine with Workers for Platforms when customers also deploy code | [SaaS docs](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/index.md) |
| Connect a Worker to storage or another service | Bindings | Give the Worker access to configured resources through its environment | [Bindings](bindings/README.md) |
| Run containerized services or Linux software | Containers | The workload needs a container image or software outside the Workers runtime | [Containers](containers/README.md) |
| Execute generated or untrusted code, build Code Mode tools, or create on-demand previews | Dynamic Workers | Load code at runtime in isolated Workers; check bindings, egress controls, and resource limits. Choose Sandbox when execution needs Linux or shell tools | [Dynamic Workers docs](https://developers.cloudflare.com/dynamic-workers/index.md) |
| Give an agent a shell, filesystem, or interactive development environment | Sandbox SDK | Code execution needs a Linux environment or container tools; inspect the package line first | `sandbox-next` for new or preview projects; `sandbox-stable` for existing stable apps; [Sandbox docs](https://developers.cloudflare.com/sandbox/index.md) |
| Upgrade a stable Sandbox app to the preview API | Sandbox SDK | The user wants the stable-to-next migration | `sandbox-migrate-to-next` skill; [migration guide](https://developers.cloudflare.com/sandbox/sdk/migrate/index.md) |
