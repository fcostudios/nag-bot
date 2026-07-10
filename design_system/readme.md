# QPH · Quito Publishing House — Design System

A design system for **Quito Publishing House (QPH)**, a corporate building ("edificio corporativo") that houses several companies and shared services. The imagotype represents the **building** (isotype = the stacked skyline bars) plus the **name** (logotype). The brand speaks to a young audience: **orange** carries optimism, sociability and creativity; the **corporate grays** add neutrality, quality, sophistication and knowledge.

QPH is an **umbrella brand**. Inside it live sub-brands (e.g. Kickoff, Opina, Right Angle Media, PPM, Focus), each with its own colors. **Never mix** a sub-brand's colors with QPH's unless the piece explicitly belongs to that company.

> This system was rebuilt from the official **Guía de Marca QPH** (brand-guide package), itself based on `brandbook_qph.pdf` (Manual de Identidad Corporativa) and the `PRESENTACION ATISCODE 2.pptx` slide template.

---

## Sources

This design system was authored from the following materials (the reader may not have access — links/paths recorded for provenance):

- **`Guia de Marca QPH/`** — brand-guide codebase (read-only, mounted locally). Contains:
  - `agentes/00-guia-maestra-marca.md` — master brand context (logo, color, type, rules).
  - `agentes/01-documentos.md` — documents, comunicados, bienvenidas (welcome pieces).
  - `agentes/02-presentaciones.md` — presentation template & slide rules.
  - `agentes/03-sistema-diseno.md` — design system spec for mocks/apps.
  - `design-tokens/qph-tokens.css` + `qph-tokens.json` — token source of truth.
  - `assets/qph-logo-{positivo,positivo-fondoblanco,negativo}.png` — logo lockups.
  - `qph-design-system-showcase.html` — a single-page showcase of the language.
  - `Manual-Marca-QPH-Resumen.docx` — human-readable summary.
- **`brandbook_qph.pdf`** — the canonical *Manual de Identidad Corporativa* (30 pp). **Reviewed directly** — this system's tokens, fonts and rules are verified against it.
- **`PRESENTACION ATISCODE 2.pdf`** — the slide template (5 layout pages: título + numbered items). **Reviewed directly.**
- **`uploads/corporativo..png`** — the new "corporativo." logo artwork (June 2026 rebrand), source for all `assets/corporativo-*` derivatives.

**Fonts:** Barlow + Josefin Sans — these are the **official brand fonts** named in the brandbook (Josefin Sans Light for the logo lettering; Barlow Black/Bold/Regular/Italic for everything else). Both are open-source (OFL) and are self-hosted here as woff2 (latin subset). No substitution.

---

## Brand essentials (memorize)

- **Logo:** the **"corporativo."** wordmark (June 2026 rebrand) — orange infinity **"co" ligature**, gray lowercase lettering, final **orange period**. Horizontal, never deformed/rotated/recolored/retyped. Use `assets/corporativo-logo.png` on light, `-negativo` on dark, `-blanco` on orange/colored; the mark alone (`corporativo-mark.png`) only at favicon/app-icon sizes. The legacy QPH bars imagotype (`assets/qph-logo-*.png`) is deprecated — don't use it in new pieces.
- **Color:** orange `#e7851a` is the single general accent; corporate grays (`#c0bfc0`, `#949394`, `#787474`, `#595756`) build structure. Each service area has its own accent color — use it only for that area's communications.
- **Type:** **Barlow** for everything (titles, UI, body). **Josefin Sans** Light only for the logo lettering.
- **Name in writing:** "Quito Publishing House" or "QPH" — never "Qph" or lowercased.
- **Maintenance cadence:** comunicados every 6 months; presentations & bienvenidas yearly.

---

## Content fundamentals — how QPH writes

- **Language:** Spanish (Ecuador). Professional but warm and optimistic — aimed at a young workforce.
- **Voice / person:** Institutional but human. Communications often address the collective ("el edificio", "los colaboradores"). Welcome pieces speak *to* and *about* the person ("BIENVENIDA/O", the new colaborador's name). Avoid stiff bureaucratic tone.
- **Casing:** Headlines are **UPPERCASE** Barlow Black — this is the brandbook's signature. Body is sentence case. The brand name is title case ("Quito Publishing House"); initials uppercase ("QPH"). Area hashtags are uppercase with `#`.
- **Exact comunicado hashtags** (verified from the brandbook): `#ADMINISTRACIÓN` · `#RSE` (Responsabilidad Social) · `#TECNOLOGÍA` · `#NÓMINA` · `#PROYECTOSYPROCESOS` · `#SEGURIDAD_INFORMACIÓN` · `#SALUD`. Each pairs with `correo@qph.com.ec` and a "Más información" call-to-action.
- **Signature heading pattern:** `SECCIÓN | TÍTULO` — a light-gray section label, an orange bar, then the title in orange, all caps. Reuse it for section headers everywhere.
- **Punctuation as decoration:** large quotation marks (" ") frame comunicado messages, in orange or the area color.
- **Emoji:** **not** part of the brand. Don't use emoji in QPH copy or UI. Use the icon-tile system instead (white pictogram on a colored rounded square).
- **Examples of tone:**
  - Headline: **"BARLOW PARA TODO"**, **"UN COLOR POR SERVICIO"**.
  - Comunicado body: *"La transformación digital del edificio arranca este trimestre con nuevas herramientas internas."*
  - Welcome: **"BIENVENIDA"** + *Ana Rafaela Ramírez* + pill *"Consultor de RRHH"*.
  - Contact pill: `correo@qph.com.ec`.
- **Comunicados empresariales (sub-brands):** when a piece belongs to a tenant company, use *that company's* colors and email domain, not QPH's. Verified domains: `correo@kickoff.com.ec` · `correo@opinno.com` · `correo@rangle.ec` (Right Angle) · `correo@ppm.com.ec` · `correo@atis-ketchum.com.ec` · `correo@focusresearch.com.ec`.
- **Bienvenida examples (from the brandbook):** *Ana Rafaela Ramírez — Consultor de RRHH*; *Victor Pesantez — Community Manager*; *Jhonny Cabrera — Buyer de Medios*; *Nicole Sampedro — Jefe de Growth*. Name in uppercase, role beneath, B&W portrait in a circular frame in the company's color.
- **Closing slide convention:** an all-orange slide with **"GRACIAS"** in Barlow Black white.

---

## Visual foundations

**Overall vibe.** Clean, spacious, confident. Lots of white space, clear hierarchy, few elements per view — "the brandbook is very uncluttered." Orange is rationed: one accent action/highlight at a time; grays do the structural work.

**Color.** Orange `#e7851a` is the only general accent. **⚠ Open question:** the new "corporativo." logo artwork samples at `#f06820` — brighter than the brandbook orange `#e7851a`. Tokens keep the brandbook value until the rebrand palette is confirmed; if `#f06820` is the new brand orange, update `--qph-orange` (+ hover/soft) in `tokens/colors.css`. Corporate grays (`#c0bfc0 → #595756`) are for text, borders and fills — structure, not decoration. `#3d3d3d` (ink) is the dark surface used in presentations and dark headers; `#f2f2f2` is the light card fill. Seven **area colors** organize each service's communication; when a piece belongs to an area, its accent becomes that area's color and nothing else changes. Sub-brand pieces drop QPH colors entirely for the sub-brand's palette.

**Imagery.** Real photography of the QPH building and team. Welcome pieces use **black-and-white (grayscale) portraits** inside a circular frame, to balance against the corporate colors. Presentation covers use a full-bleed building photo with a dark `#3d3d3d` veil at ~70–80% opacity and white Barlow Black title over it. Warm/neutral, never garish.

**Type.** Barlow throughout — Black 900 for uppercase headlines, Bold 700 for subheads/emphasis, SemiBold 600 for leads, Regular 400 for body, Italic for nuance (and for role pills). Josefin Sans Light is reserved for the logo. Headlines are tight-leading uppercase; body is 1.5 line height with generous measure.

**Spacing & layout.** 4px spacing scale. Content max-width 1200px, centered, with wide margins. Generous padding inside cards (24px). The system favors air over density.

**Backgrounds.** Mostly flat white or flat ink `#3d3d3d`. **No gradients** as a brand device (the dark photo veil is the one exception). No repeating textures or patterns. Decorative geometry is limited to **orange arcs, rings and dots** (echoing the circular welcome frames and the "bubbles" motif) and **numeric badges** in orange squares.

**Corners & cards.** Cards: white fill, 1px `#e3e2e2` border, 16px radius (`lg`), soft `shadow-sm`/`md`, 24px padding. Buttons & inputs: 8px radius (`md`). Chips/pills: full 999px radius. Small inputs: 4px (`sm`).

**Shadows.** Soft and **gray-tinted** (`rgba(89,87,86,…)` / `rgba(61,61,61,…)`) — never pure black. Three steps: sm (rest), md (raised/hover), lg (overlays).

**Borders.** Hairline `#e3e2e2` for dividers and card edges; `1.5px` `#949394` for secondary-button outlines; the focus ring is a 2–3px orange-100 glow with an orange border.

**Motion.** Subtle and quick. ~150ms ease `cubic-bezier(0.2,0,0.2,1)` for hovers; ~250ms for larger transitions. Fades and small translateY lifts on cards. No bounces, no infinite decorative loops.

**Hover states.** Primary button darkens orange (`#e7851a → #c96f12`); secondary fills with `#f2f2f2`; ghost fills with orange-100; cards lift `translateY(-2px)` and deepen shadow; nav links gain an orange underline.

**Press / active.** Slightly darker fill (orange-600); active nav/link shows orange.

**Transparency & blur.** Used sparingly: the sticky header uses `rgba(255,255,255,0.92)` + `backdrop-filter: blur(8px)`; the presentation cover uses a semi-opaque dark veil over photography.

**Accessibility.** Orange on white does **not** meet AA for small text — use it for large elements, fills and accents. Body text is gray-700 on white (AA). Always keep a visible orange focus ring.

---

## Iconography

- **Style:** the brandbook (p.16, *Iconografía*) calls pictograms "un recurso visual fundamental para generar interés" and specifies they use the **principal and secondary corporate colors**, depending on whether the context is general or area-specific. So: flat, single-figure pictograms, tinted in orange / gray / the relevant area color (here rendered as white-on-color tiles). One figure per icon.
- **No emoji.** Emoji are not a brand device. Where the legacy showcase used emoji in cards, this system replaces them with proper icon tiles.
- **No bespoke unicode glyphs** as icons (except the large decorative quotation marks " " in comunicados, which are a typographic motif, not an icon).
- **Icon set used here:** the brandbook **defines no specific icon font or named library** — only the pictogram *style* and color rules above. This system therefore uses **[Lucide](https://lucide.dev)** (clean, consistent 2px stroke) as a faithful stand-in. **⚠ If QPH has a specific pictogram set, send it and I'll swap it in.** (Note: I could not auto-extract the brandbook's pictogram artwork — those PDF pages use transparency groups that hang the renderer — so the visual match is based on the documented style, not a pixel trace.)
- **Logos** live in `assets/`: `corporativo-logo.png` (positive), `corporativo-logo-negativo.png` (white lettering, on dark), `corporativo-logo-blanco.png` (all white, on orange/colored), `corporativo-mark.png` (infinity mark, favicon sizes only). Legacy QPH lockups (`qph-logo-*.png`) are kept for archive only.

---

## Index / manifest

**Root**
- `styles.css` — the only file consumers link (imports fonts + all tokens).
- `readme.md` — this guide.
- `SKILL.md` — Agent Skill manifest (portable to Claude Code).

**Tokens** (`tokens/`)
- `colors.css` · `typography.css` · `spacing.css` · `effects.css`

**Fonts & assets** (`assets/`)
- `fonts.css` + `fonts/*.woff2` — Barlow & Josefin Sans (self-hosted).
- `qph-logo-*.png` — logo lockups.

**Foundation cards** (`guidelines/*.card.html`) — Design System tab specimens for Colors, Type, Spacing, Brand.

**Components** (`components/`) — reusable React primitives, grouped:
- `core/` — **Button**, **Badge** (numeric), **Pill** (role chip), **Card**.
- `forms/` — **Input**, **Select**, **Switch**.
- `feedback/` — **Alert**, **Tag**, **Progress**.
- `brand/` — **Logo** (CSS lockup), **IconTile**, **AreaTag** (+ `QPH_AREAS` map).
Each directory has a `*.card.html` specimen, `<Name>.d.ts` props, and `<Name>.prompt.md` usage.

**UI kits** (`ui_kits/`) — interactive, self-contained product recreations:
- `intranet/` — corporate intranet: login → dashboard (stats, comunicados feed, areas) → comunicados (area-filtered, new-comunicado modal) → colaboradores (bienvenida-style directory) → áreas.
- `comunicados/` — brand artifact studio: live comunicado (speech-bubble) and bienvenida (welcome) previews, switchable by area/format with editable copy.

**Slides** (`slides/`) — ATISCODE 4:3 sample deck, one HTML per layout:
- `01-portada` (cover) · `02-lista` (numbered list) · `03-galeria` (4-image gallery) · `04-tarjetas` (3 cards) · `05-timeline` · `06-gracias` (orange closing). Shared styling in `slides.css`.

**Skill** — `SKILL.md` (root): Agent-Skill manifest, portable to Claude Code.

> **Starting points** (for consuming projects): Button, Card, and Logo are tagged as component starting points; UI-kit screens render from each kit's `index.html`.
