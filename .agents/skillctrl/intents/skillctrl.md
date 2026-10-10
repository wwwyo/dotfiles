# Skill management ownership

The shared dotfiles skills contain both imported skills and handwritten workflows. Keep upstream registration as the boundary for accepted hashes and adaptation: handwritten skills remain outside that workflow even when they have saved intent. Do not invent an upstream source to make recording succeed.

Management guidance must match the installed CLI's acceptance rules. Accept deliberate edits only for registered upstream skills after inspecting their complete installed directory. Preserve caller staging and immutable source snapshots, and leave unrelated registered hashes unchanged.

Preserve our mise-based acquisition setup when adapting management guidance. Reusing a compatible mise-pinned `skills` executable keeps imports reproducible under the shared version policy instead of introducing a second installation path; dependency advice should continue to respect that setup.

Keep the authoring guidance that makes skills verifiable and safe in this environment: external-service capabilities are checked against the live CLI/API before being written down, credential headers are never combined with redirect-following HTTP, and runtime-dependent capabilities are described conditionally rather than hardcoded.
