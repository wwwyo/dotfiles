# 開発・テスト・deploy・API

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Run locally and manage resources from the CLI | Wrangler | Develop, configure, deploy, and inspect the intended account and environment | `wrangler` skill; [Wrangler docs](https://developers.cloudflare.com/workers/wrangler/index.md) |
| Test Worker behavior before deployment | Workers testing tools | Choose runtime tests or integration tests for the affected behavior | [Testing docs](https://developers.cloudflare.com/workers/testing/index.md); `durable-objects` skill for DO tests |
| Embed local Worker simulation in tooling | Miniflare | A programmatic emulator is needed for a custom development or test harness | [Miniflare](miniflare/README.md) |
| Run or investigate the underlying Workers runtime | workerd | Work directly with the runtime outside normal managed deployment | [workerd](workerd/README.md) |
| Try a small Worker in the browser | Workers Playground | Explore or share a minimal example without local setup | [Workers Playground](workers-playground/README.md) |
| Build and deploy whenever code is pushed | Workers Builds | Connect a Git repository to automated builds and deployments | [Builds docs](https://developers.cloudflare.com/workers/ci-cd/builds/index.md) |
| Test a branch or pull request in an isolated environment | Workers Previews | Create a branch environment under the same Worker with its own settings and URLs; check which bound resources are isolated or shared | [Previews docs](https://developers.cloudflare.com/workers/previews/index.md); `wrangler` skill |
| Inspect an uploaded version, release it gradually, or roll back code | Workers versions and deployments | Manage application releases that use production resources; rollback does not restore connected resource data | [Deployment docs](https://developers.cloudflare.com/workers/versions-and-deployments/index.md); `wrangler` skill |
| Release a feature gradually or target user groups | Flagship | Change feature availability with targeting and percentage rollouts | [Flagship](flagship/README.md) |
| Manage infrastructure as code | Terraform or Pulumi | Use Terraform for declarative configuration or Pulumi for infrastructure in programming languages | [Terraform](terraform/README.md); [Pulumi](pulumi/README.md) |
| Automate account or product configuration through an API | Cloudflare REST API | Manage resources programmatically; prefer bindings for supported operations inside Workers | [REST API](api/README.md) |
