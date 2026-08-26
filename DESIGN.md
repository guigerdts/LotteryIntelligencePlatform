---
name: Esmeralda Fortuna — Lottery Intelligence Platform
description: Warm, trustworthy, green-led design system for a Colombian lottery-intelligence product that is honest about odds.
colors:
  lucido-emerald: "#0E8A5F"
  lucido-emerald-deep: "#0A6E4A"
  lucido-emerald-mist: "#E5F3EC"
  fortune-gold: "#C8922B"
  fortune-gold-cream: "#F8EFD9"
  warm-paper: "#FAF8F3"
  pure-surface: "#FFFFFF"
  warm-panel: "#F1ECE3"
  ink: "#1B2320"
  ink-muted: "#4C5550"
  ink-faint: "#6B736E"
  warm-border: "#E4DED3"
  warm-border-strong: "#D6CEC0"
  growth-green: "#1F9D57"
  growth-green-mist: "#E5F3EC"
  amber-warning: "#B7791F"
  amber-cream: "#FBF1DD"
  clay-red: "#C0392B"
  clay-red-mist: "#FAE9E6"
  info-blue: "#2563EB"
  info-blue-mist: "#E8EEFB"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontWeight: 600
    fontSize: "18px"
    lineHeight: 1.3
  body:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontWeight: 400
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontWeight: 600
    fontSize: "12px"
    letterSpacing: "0.05em"
    textTransform: "uppercase"
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.lucido-emerald}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  button-primary-hover:
    backgroundColor: "{colors.lucido-emerald-deep}"
  button-secondary:
    backgroundColor: "{colors.fortune-gold}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  button-ghost:
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  input:
    backgroundColor: "{colors.pure-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  chip-selected:
    backgroundColor: "{colors.lucido-emerald-mist}"
    textColor: "{colors.lucido-emerald}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  card:
    backgroundColor: "{colors.pure-surface}"
    rounded: "{rounded.md}"
    padding: "16px"
  nav-active:
    backgroundColor: "{colors.warm-panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: Esmeralda Fortuna

## Overview

**Creative North Star: "The Lucid Garden of Odds"**

Esmeralda Fortuna is a Colombian lottery-intelligence platform with a deliberate, slightly warm personality: trust and luck, led by a confident green. The product never sells a win — it explains the odds with calm clarity. The interface should feel like a well-tended garden: ordered, legible, and quietly optimistic, where the accent earns its presence rather than shouting. Familiarity is a feature here (this is an operate-mode product UI), so restraint is the floor; the user chose a bold/warm brand, so the accent is allowed a confident, slightly expressive voice — but always in service of understanding, never decoration.

Surfaces carry a warm paper tint rather than clinical white-on-gray, which keeps long analysis sessions comfortable. The single green accent owns primary actions and current selection; a sparing gold appears only for "lucky" or featured moments. Status is always communicated with color **and** icon **and** text, because honesty about odds demands that nothing rides on color alone.

**Key Characteristics:**
- Green-led, warm-neutral, trust-forward operate-mode product UI.
- One confident accent (Lucido Emerald) used with discipline; gold reserved for featured/lucky.
- Every surface is warm-tinted; pure white appears only as an elevated card.
- Status is multi-coded (color + icon + text), never color-only.
- Familiar component vocabulary; consistency across screens is the virtue.

## Colors

A warm, green-led palette. Lucido Emerald is the only brand accent; Fortune Gold is a rare featured/lucky highlight; neutrals are warm-tinted; semantic colors (success/warning/error/info) are standardized and never overloaded for actions.

### Primary
- **Lucido Emerald** (#0E8A5F): The brand accent. Owns primary actions (generate, compute), current selection, focus rings, and the selected/filter chip. Deep variant (#0A6E4A) is the hover state; Mist (#E5F3EC) is the selection fill.
- **Fortune Gold** (#C8922B): Reserved for "lucky" or featured moments only (e.g. a highlighted result), used sparingly. Cream (#F8EFD9) is its soft fill.

### Secondary (optional; used as rare featured accent)
- **Fortune Gold** (#C8922B): A second accent that must never compete with the emerald for attention; treat as decorative emphasis, not an action color.

### Neutral
- **Warm Paper** (#FAF8F3): App canvas / page background. Never pure white.
- **Pure Surface** (#FFFFFF): Elevated cards and inputs only.
- **Warm Panel** (#F1ECE3): Secondary panels, table headers, hover and selected-nav fills.
- **Ink** (#1B2320): Primary text and headings.
- **Ink Muted** (#4C5550): Secondary text, labels.
- **Ink Faint** (#6B736E): Tertiary text — use only on light surfaces where it clears 4.5:1 (fails on Warm Panel; see rules).
- **Warm Border** (#E4DED3): Default hairline borders. **Warm Border Strong** (#D6CEC0): Emphasized borders, focus rings on neutral controls.

### Semantic
- **Growth Green** (#1F9D57, Mist #E5F3EC): Success / positive status (with icon + text).
- **Amber Warning** (#B7791F, Cream #FBF1DD): Warning / caution callouts.
- **Clay Red** (#C0392B, Mist #FAE9E6): Error / failure status (with icon + text).
- **Info Blue** (#2563EB, Mist #E8EEFB): Informational links/state only — explicitly NOT an action or selection color, to avoid the old accent-collision trap.

### Named Rules
**The One Accent Rule.** Lucido Emerald owns ≤10% of any screen and is used for primary actions and current selection only. Its rarity is the point; scattering it dilutes trust.

**The Honest Status Rule.** Every status uses color + icon + text, never color alone. A red error with no label, or a green success with no words, is not allowed.

**The Warm Neutral Rule.** All surfaces carry a warm paper tint (Warm Paper / Warm Panel); pure white appears only as an elevated card, never as a page background.

## Typography

**Display Font:** Inter (with system-ui, -apple-system, Segoe UI, Roboto fallback)
**Body Font:** Inter (same stack)
**Label/Mono Font:** Inter for labels; `font-mono` (system mono) for checksums, fingerprints, and IDs.

**Character:** One confident sans carries the whole product. Headings are semibold and close in scale to body (operate-mode density); labels are small, uppercase, and tracked. No display face — familiarity over flourish.

### Hierarchy
- **Display** (600, 18px / 1.3): Page and section headings (text-lg equivalent).
- **Body** (400, 14px / 1.5): Default UI text, table cells, descriptions.
- **Label** (600, 12px, 0.05em, uppercase): Column headers, group titles, eyebrows.

### Named Rules
**The One Family Rule.** A single sans (Inter) serves display, body, and label. Do not introduce a second typeface for product UI.

**The Readable Secondary Rule.** Secondary text is Ink Muted (#4C5550) on light surfaces. Ink Faint (#6B736E) is for non-essential text on white only; on Warm Panel it falls below 4.5:1, so promote it to Ink Muted there.

## Layout

A fixed application shell: top header (brand + global lottery selector) over a left grouped navigation rail and a scrollable main content area, all on the Warm Paper canvas. Content uses a consistent 16px (md) spacing rhythm and `space-y-6` section gaps; pages pad with `p-4 sm:p-6`. Cards and tables are the dominant unit; density is allowed (operate-mode) but never at the cost of the warm, calm feel. Responsive behavior is structural (collapsing sidebar, breakpoint columns) — not fluid typography.

## Elevation & Depth

Depth is conveyed by a layered tonal system plus a restrained, soft shadow scale. At rest, cards sit on Warm Paper as Pure Surface with a hairline Warm Border and the smallest shadow (`shadow-sm`). Elevation and hover lift the shadow one step (`shadow-md`); focus uses a 2px ring, not a shadow. The system is "flat by default, lifted by state."

### Shadow Vocabulary
- **shadow-sm** (`0 1px 2px rgba(27,35,32,0.06)`): Resting card / input.
- **shadow-md** (`0 4px 12px rgba(27,35,32,0.08)`): Hover / interactive elevation.
- **shadow-lg** (`0 12px 32px rgba(27,35,32,0.12)`): Transient overlays or prominent surfaces.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. Shadows appear only as a response to state (hover, elevation, focus ring), never as constant decoration.

## Shapes

Gently rounded, consistent corners: `rounded-md` (10px) is the form language for buttons, inputs, cards, chips, and nav items; `rounded-sm` (6px) for compact marks; `rounded-lg` (16px) for larger containers. Borders are hairline Warm Border; interactive controls gain a 2px focus ring (emerald for actions, Warm Border Strong for neutral controls). No hard 0px corners, no oversized radii.

## Components

### Buttons
- **Shape:** Gently rounded (10px / `rounded-md`), comfortable padding (8px 12px), medium weight.
- **Primary:** Lucido Emerald fill, white label; hover → Lucido Emerald Deep; focus-visible → 2px emerald ring; disabled → 50% opacity + not-allowed; loading → spinner + disabled.
- **Secondary (Fortune Gold):** Gold fill, white label; hover → 90% opacity; used only for featured/lucky emphasis.
- **Ghost:** Ink Muted text on transparent; hover → Warm Panel fill + Ink text.
- **Outline:** Ink text, Warm Border; hover → Warm Panel fill.
- Sizes sm/md/lg cover the action scale.

### Chips (selection / filter)
- **Selected:** Lucido Emerald Mist fill, Lucido Emerald text, emerald border — used for the active snapshot / filter selection. This is SELECTION, not an action, so it must never read as a primary button.
- **Unselected:** Pure Surface fill, Ink Muted text, Warm Border; hover → Warm Panel.

### Cards / Containers
- **Corner Style:** 10px (`rounded-md`).
- **Background:** Pure Surface (white) — the only place pure white appears.
- **Shadow Strategy:** `shadow-sm` at rest, `shadow-md` on interactive hover.
- **Border:** Hairline Warm Border.
- **Internal Padding:** 16px (`p-4`) by default.

### Inputs / Fields
- **Style:** Pure Surface fill, Ink text, Warm Border, 10px radius.
- **Focus:** Border shifts to Lucido Emerald, 2px emerald focus ring.
- **Error / Disabled:** Error-tinted border for invalid; disabled → Warm Panel fill + 50% opacity + not-allowed.

### Navigation
- **Style:** Grouped rail; each item is a full-width rounded row, medium weight.
- **Default:** Ink Muted text on transparent; hover → Warm Panel fill + Ink text.
- **Active (aria-current="page"):** Warm Panel fill + Ink text — deliberately NOT emerald, so the active tab never collides with a primary action button.
- **Focus:** 2px emerald focus-visible ring.

## Do's and Don'ts

### Do:
- Do use Lucido Emerald for primary actions and current selection only (The One Accent Rule).
- Do communicate every status with color + icon + text (The Honest Status Rule).
- Do keep all surfaces warm-tinted; use pure white only for elevated cards.
- Do use Warm Panel for the active nav item, not emerald.
- Do promote secondary text on Warm Panel to Ink Muted to stay ≥4.5:1.

### Don't:
- Don't use blue (the legacy accent) for actions or selection — emerald owns those roles now.
- Don't turn a selected/filter chip into a solid emerald button; selection uses Emerald Mist, action uses solid emerald.
- Don't put Ink Faint (#6B736E) on Warm Panel — it fails WCAG AA body contrast.
- Don't overload Fortune Gold; it is a rare featured/lucky highlight, not a second action color.
- Don't invent radii outside the 6/10/16px scale.
