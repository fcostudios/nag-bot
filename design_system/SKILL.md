---
name: qph-design
description: Use this skill to generate well-branded interfaces and assets for Corporativo, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the `readme.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick map
- `readme.md` — full brand guide: context, content fundamentals, visual foundations, iconography, manifest. **Read this first.**
- `styles.css` — the only stylesheet to link; `@import`s fonts + all tokens.
- `tokens/` — colors, typography, spacing, effects (CSS custom properties).
- `assets/` — logos (`qph-logo-positivo.png`, `qph-logo-negativo.png`) + self-hosted fonts.
- `components/` — React primitives (Button, Card, Badge, Pill, Input, Select, Switch, Alert, Tag, Progress, Logo, IconTile, AreaTag).
- `guidelines/*.card.html` — foundation specimen cards.
- `ui_kits/intranet/` — corporate intranet recreation (login → dashboard → comunicados → colaboradores).
- `ui_kits/comunicados/` — comunicado + bienvenida studio (the brand's signature artifacts).
- `slides/` — ATISCODE 4:3 sample slides (cover, numbered list, gallery, cards, timeline, gracias).

## Non-negotiables
- Orange `#e7851a` is the only general accent; corporate grays build structure. Use an area color only for that area's pieces. (The 2026 "corporativo." logo art samples at `#f06820` — see readme "Color" for the open question.)
- **Barlow** for everything; the logo wordmark is fixed artwork — never retype it.
- Always use the full **"corporativo."** wordmark (`assets/corporativo-logo*.png`): positive on light, negativo on dark, blanco on orange; the infinity mark alone only at favicon sizes. Never deform/recolor/rotate. Legacy QPH bars lockup is deprecated.
- Clean and spacious. No emoji. No gradients (except the photo veil on covers). Soft gray-tinted shadows.
- Write the name as "Corporativo".
