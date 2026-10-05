# 推論・検索・agents・browser

Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Run language, embedding, image, or speech models | Workers AI | Use managed inference; verify model capabilities, schemas, and pricing | [Workers AI](workers-ai/README.md) |
| Add managed search or answers over your content | AI Search | Use a managed retrieval-augmented generation pipeline | [AI Search](ai-search/README.md) |
| Build custom semantic search or retrieval | Vectorize + Workers AI | Control embeddings, indexing, and retrieval rather than using a managed pipeline | [Vectorize](vectorize/README.md); [Workers AI](workers-ai/README.md) |
| Observe and control requests to AI providers | AI Gateway | Add inference analytics, caching, and request controls | [AI Gateway](ai-gateway/README.md) |
| Build stateful agents with tools, scheduling, or chat | Agents SDK | Implement agent behavior on Cloudflare; add Dynamic Workers or Sandbox for the required execution runtime | `agents-sdk` skill; [Agents docs](https://developers.cloudflare.com/agents/index.md) |
| Build durable agents with TypeScript hooks | Flue | Use an open agent framework with Cloudflare and Node.js targets | [Flue](https://flueframework.com/); [getting started](https://flueframework.com/docs/guide/getting-started/); [Cloudflare target](https://flueframework.com/docs/guide/cloudflare-target/) |
| Expose tools through a remote MCP server | Workers + Agents SDK | Publish tools for MCP clients, with authentication appropriate to the service | `agents-sdk` skill, its `references/mcp.md`; [MCP docs](https://developers.cloudflare.com/agents/model-context-protocol/index.md) |
| Automate browsers, take screenshots, or extract rendered pages | Browser Run | The task requires a browser rather than a plain HTTP request | [Browser Run](browser-rendering/README.md) |
