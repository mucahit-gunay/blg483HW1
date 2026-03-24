# Design System Specification: The Kinetic Ledger

This document defines the visual and structural language for a high-performance web crawling ecosystem. Our objective is to move away from the "bootstrap dashboard" aesthetic and toward a high-end, technical editorial experience that communicates precision, depth, and systemic health.

---

## 1. Creative North Star: "The Digital Cartographer"
The design system is built on the metaphor of a digital cartographer—mapping the vastness of the web with clinical precision. We avoid the "flat" look of traditional SaaS by using **Tonal Layering** and **Atmospheric Depth**.

* **Intentional Asymmetry:** Break the rigid grid by offsetting data density. Use wide margins for high-level stats and condensed, high-density modules for logs.
* **Technical Elegance:** We use `Space Grotesk` to provide a "engineered" feel to headings, contrasted by the utilitarian legibility of `Inter` for data.
* **The "Living" System:** Movement and health are communicated through the `tertiary` (Emerald) palette, suggesting a biological vitality within a cold, mechanical structure.

---

## 2. Color & Surface Architecture
We do not use lines to define space. We use light and depth.

### The "No-Line" Rule
**Strict Prohibition:** 1px solid borders for sectioning are forbidden.
Boundaries must be defined solely through background color shifts. For example:
* A `surface-container-low` (#131B2E) sidebar sitting against a `surface` (#0B1326) main content area.
* A `surface-container-highest` (#2D3449) header providing a natural shelf for navigation.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. Use the following tiers to define importance:
1. **Base:** `surface` (#0B1326) - The foundation.
2. **Sectioning:** `surface-container-low` (#131B2E) - For large layout blocks.
3. **Interaction Hubs:** `surface-container` (#171F33) - For the main dashboard cards.
4. **Focused Data:** `surface-container-highest` (#2D3449) - For active elements or modals.

### The "Glass & Gradient" Rule
To elevate the "technical" feel, use **Glassmorphism** for floating elements (tooltips, dropdowns).
* **Token:** `surface-container-high` at 60% opacity with a `20px` backdrop-blur.
* **Signature Gradients:** Use a subtle linear gradient from `primary` (#7BD0FF) to `on_primary_container` (#008ABB) for primary action states to give them a "lucid" glow.

---

## 3. Typography
The interplay between a geometric sans-serif and a high-legibility workhorse creates an editorial hierarchy.

* **Display & Headlines (Space Grotesk):** These are the "labels of authority." Use `display-md` for macro-stats (e.g., total pages crawled). The wide apertures of Space Grotesk communicate modernism and technical scale.
* **Body & Labels (Inter):** All data-heavy logs, URLs, and status messages use `body-sm` or `label-md`.
* **Technical Stats:** For log timestamps and status codes, use `label-sm` with a `0.05rem` letter-spacing to enhance the "machine-read" aesthetic.

---

## 4. Elevation & Depth: Tonal Layering
We achieve hierarchy through **Tonal Layering** rather than drop shadows or strokes.

* **The Layering Principle:** To lift a card, do not add a shadow. Instead, move it one step up the surface scale. Place a `surface-container-lowest` (#060E20) code block inside a `surface-container` (#171F33) card to create "inset" depth.
* **Ambient Shadows:** If an element must "float" (e.g., a flyout menu), use a shadow color of `surface_container_lowest` at 40% opacity with a 32px blur. It should feel like an ambient occlusion, not a hard shadow.
* **The "Ghost Border":** For high-density data tables where separation is critical, use `outline-variant` (#45464D) at **15% opacity**. This creates a "suggestion" of a boundary that disappears into the background.

---

## 5. Signature Components

### Progress Bars (The Pulse)
* **Track:** `surface-container-highest`.
* **Indicator:** A gradient from `tertiary` (#4EDE03) to `on_tertiary_container` (#009365).
* **Detail:** Add a subtle outer glow to the indicator using the `tertiary` color at 20% opacity to suggest "active power."

### Status Badges
* **Active/Healthy:** `tertiary_container` background with `on_tertiary` text. No borders.
* **Crawling/Processing:** `primary_container` background with `primary` text.
* **Error:** `error_container` background with `on_error_container` text.
* **Shape:** Use `rounded-sm` (0.125rem) for a more technical, "chip-set" appearance.

### Data Lists & Logs
* **Separation:** Forbid dividers. Use a `1.5` (0.3rem) vertical gap between items.
* **Alternating Tones:** Use a very subtle shift between `surface` and `surface-container-lowest` for alternating rows to maintain readability in high-density views.
* **Search Results:** Titles use `title-md` in `primary`. Metadata (URLs, timestamps) must use `body-sm` in `on_surface_variant`.

### Buttons
* **Primary:** `primary` (#7BD0FF) background with `on_primary` (#00354A) text. Use `rounded-md`.
* **Tertiary (Ghost):** No background. Text in `primary`. On hover, apply a `surface-bright` background at 10% opacity.

---

## 6. Do’s and Don’ts

### Do
* **Do** use `20` (4.5rem) and `24` (5.5rem) spacing for major layout gutters to give the technical data "room to breathe."
* **Do** use `tertiary` (Emerald) sparingly. It is a signal of life/activity, not a decorative color.
* **Do** stack `surface-container` tiers to create logical grouping.

### Don’t
* **Don’t** use 100% white (#FFFFFF). The brightest text should be `on_surface` (#DAE2FD) to reduce eye strain in high-density data environments.
* **Don’t** use `rounded-full` for functional components. Stick to `sm` or `md` to maintain the architectural, technical aesthetic.
* **Don’t** use standard "Blue" for links. Use the `primary` token (#7BD0FF) to ensure it sits correctly within the deep blue environment.

---

## 7. Interaction Micro-copy
In a web crawler, the "system is the star." Use technical, active language in the UI:
* Instead of "Loading," use `INITIALIZING_STREAM...`
* Instead of "Error," use `CRAWL_INTERRUPTED_V.01`
* Instead of "Done," use `INDEX_COMPLETE`

This reinforces the "Digital Cartographer" persona, making the user feel they are operating a sophisticated piece of machinery.