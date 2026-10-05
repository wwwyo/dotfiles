# Glossary Format

## Structure

```md
## Glossary

**Order**:
{A one or two sentence description of the term}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account
```

## Rules

- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions tight.** One or two sentences max. Define what it IS, not what it does.
- **Only include terms specific to this project's context.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the project uses them extensively. Before adding a term, ask: is this a concept unique to this context, or a general programming concept? Only the former belongs.
- **Only terms on par with model definitions belong.** Nouns for things/entities (documents, records, deliverables, layers) — not names of processes, procedures, or checks. If a term is something you *do* (extract, validate, reconcile) rather than something that *is*, fold its description into the related entity's note instead of giving it its own entry.
- **Write the English name used in code next to the term** (e.g. `**原典（origin）**`, `**正規化（staging）**`), so readers can map glossary terms to identifiers.
- **Group terms under subheadings** when natural clusters emerge. If all terms belong to a single cohesive area, a flat list is fine.
