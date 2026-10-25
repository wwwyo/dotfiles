# DNS・TLS・network・security

Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Connect a domain, configure DNS records, or troubleshoot resolution | DNS | Manage authoritative records and choose whether traffic is proxied through Cloudflare | [DNS docs](https://developers.cloudflare.com/dns/index.md) |
| Configure HTTPS and certificates | SSL/TLS | Secure connections from visitors to Cloudflare and from Cloudflare to the origin | [SSL/TLS docs](https://developers.cloudflare.com/ssl/index.md) |
| Distribute traffic across origins and fail over unhealthy servers | Load Balancing | Use health checks and traffic steering for multiple origin servers | [Load Balancing docs](https://developers.cloudflare.com/load-balancing/index.md) |
| Connect an existing server to Cloudflare | Cloudflare Tunnel | Reach an origin without a publicly routable IP address | [Tunnel](tunnel/README.md) |
| Connect Workers to private services | Workers VPC | Access services in private networks from a Worker | [Workers VPC](https://developers.cloudflare.com/workers-vpc/index.md) |
| Require employee login before accessing an internal app | Access | Put identity-based access policies in front of an internal application | `cloudflare-one` skill; [Access docs](https://developers.cloudflare.com/cloudflare-one/access-controls/index.md) |
| Transform permitted Gateway HTTP traffic with a Worker | Gateway Forward + Workers | Apply custom request or response logic to traffic passing through Gateway | `gateway-workers` skill |
| Protect access to internal applications and networks | Cloudflare One | Apply identity and network access policies | `cloudflare-one` skill; [Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/index.md) |
| Migrate existing access and network security configurations | Cloudflare One | The task is a supported migration to Cloudflare One | `cloudflare-one-migrations` skill; [Cloudflare One docs](https://developers.cloudflare.com/cloudflare-one/index.md) |
| Proxy a TCP or UDP application | Spectrum | Protect and accelerate non-HTTP application traffic | [Spectrum](https://developers.cloudflare.com/spectrum/index.md) |
| Connect a network directly to Cloudflare | Network Interconnect | Dedicated network connectivity is required | [Network Interconnect](https://developers.cloudflare.com/network-interconnect/index.md) |
| Improve routing across the network | Argo Smart Routing | Optimize traffic paths to the origin | [Argo Smart Routing](https://developers.cloudflare.com/argo-smart-routing/index.md) |
| Reduce Worker-to-backend latency | Smart Placement | Place Worker execution closer to the backends it calls | [Smart Placement](smart-placement/README.md) |
| Redirect URLs, rewrite paths or headers, or change origin routing | Rules | Use Redirect, Transform, or Origin Rules when configuration can express the required behavior | [Rules docs](https://developers.cloudflare.com/rules/index.md) |
| Make small HTTP request or response changes | Snippets | Lightweight edge logic meets the need | [Snippets](https://developers.cloudflare.com/rules/snippets/index.md) |
| Protect forms from automated abuse | Turnstile | Add bot challenges and server-side token validation | `turnstile-spin` skill; [Turnstile docs](https://developers.cloudflare.com/turnstile/index.md) |
| Filter malicious web requests | WAF | Apply application-layer rules and managed protections | [WAF](waf/README.md) |
| Protect services from denial-of-service attacks | DDoS Protection | Mitigate attacks at the relevant network or application layer | [DDoS protection](https://developers.cloudflare.com/ddos-protection/index.md) |
| Detect and control automated traffic | Bot Management | Make request decisions based on bot detection | [Bot Management](https://developers.cloudflare.com/bots/index.md) |
| Discover and protect API endpoints | API Shield | Apply API-specific protections and validation | [API Shield](https://developers.cloudflare.com/api-shield/index.md) |
| Queue visitors during traffic spikes | Waiting Room | Control admission when application capacity is limited | [Waiting Room docs](https://developers.cloudflare.com/waiting-room/index.md) |
| Store a Worker's API keys and credentials | Workers secrets | Bind secrets to a Worker without committing values to source | `wrangler` skill; [secrets docs](https://developers.cloudflare.com/workers/configuration/secrets/index.md) |
| Share managed secrets across services | Secrets Store | Manage reusable account-level secrets | [Secrets Store](secrets-store/README.md) |
| Control where data is processed and stored | Data Localization Suite | Evaluate regional processing and storage controls against the actual requirements | [Data Localization docs](https://developers.cloudflare.com/data-localization/index.md) |
| Prove a claim without identifying or tracking the user | Privacy Pass | Use privacy-preserving tokens in a supported integration | [Privacy Pass docs](https://developers.cloudflare.com/privacy-pass/index.md) |
