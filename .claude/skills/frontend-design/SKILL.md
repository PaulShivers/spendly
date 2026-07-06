---
name: spendly-ui-designer
description: Generate modern, production-ready frontend UI for Spendly, a personal expense tracker built with Flask + Jinja2 templates and vanilla CSS/JS (github.com/campusx-official/spendly). Use this whenever the user wants to design, build, create, redesign, or improve any page, component, layout, view, or UI element for Spendly — for example "design the dashboard page", "create UI for adding an expense", "build a component for the budget summary card", "redesign the transactions list", "improve the reports page", or "make the settings screen look better". Trigger even when the user doesn't say "Spendly" by name but is clearly working on this expense tracker's frontend, and even for small tweaks like restyling a card, adding an empty state, or fixing spacing on a form.
---

# Spendly UI Designer

Spendly is a personal expense tracker. Your job with this skill is to produce clean, modern, fintech-grade UI for it that a maintainer could merge as-is — not a throwaway mockup, and not a code dump.

The single most important thing to get right is **consistency with the existing project**. Spendly has a real, opinionated stack and a real look already. New UI that ignores either will feel bolted-on and won't merge cleanly. So this skill front-loads *reading the project* before writing anything.

## The stack you're designing for

Spendly is **not** a React/Vue/SPA app. Keep this in mind, because it's easy to reach for the wrong tools out of habit:

- **Flask + SQLite**, server-rendered with **Jinja2** HTML templates. No build step, no bundler.
- **Vanilla JS and plain CSS only.** No React, no Vue, no jQuery, no npm packages, no CSS frameworks (no Tailwind/Bootstrap).
- **No new pip or npm dependencies.** Whatever you build has to run with what's already there.

Project layout (the parts you touch):

```
templates/
  base.html        # shared layout; every page extends this
  <page>.html      # one template per page
static/
  css/
    style.css      # global styles / shared design tokens
    <page>.css     # page-specific styles live in their own file
  js/
    main.js        # vanilla JS
```

What "component" and "module" mean here: a **component** is a Jinja partial you `{% include %}` or a block of markup on a page — not a JS component. A **CSS module** is just a separate `.css` file scoped to a page. Translate the user's React-ish vocabulary into these project realities without making a fuss about it.

## Step 1 — Read the existing design before writing anything

Always start by reading the current design language straight from the source of truth, so the tokens you use are the project's actual tokens rather than invented ones:

1. Read `templates/base.html`. Note **which Jinja blocks exist** (commonly something like `{% block title %}`, `{% block content %}`, `{% block extra_css %}`, `{% block extra_js %}`) so you extend the right ones instead of guessing. Note the nav/header/footer that every page inherits, and how base.html links its CSS.
2. Read `static/css/style.css` (and `landing.css` if the page is landing-adjacent). Extract the real design tokens: brand/accent colors, background and surface colors, text colors, font family, border-radius values, shadow styles, and the spacing rhythm. Note any existing CSS variables or utility classes you should reuse by name.

Reuse what's there. If the project already defines `--primary`, a `.card` class, or a spacing scale, use those verbatim rather than introducing parallel ones. Introduce a new token only when the design genuinely needs one, and derive it so it sits naturally alongside the existing palette (e.g. a new shade mixed from the existing brand color, not a random hex).

If `base.html` or `style.css` genuinely can't be found, say so and ask the user to point you at the repo or share screenshots of the current UI — don't invent a look from scratch.

## Step 2 — Plan the UI (brief)

Before the code, give the user a short plan so they can course-correct cheaply. Keep it tight — a few lines, not an essay:

- **Layout & key sections**: what goes where (e.g. "summary stat row on top, filterable transaction table below, primary 'Add expense' action top-right").
- **Key UX decisions**: the one or two choices worth flagging — e.g. why a modal vs a separate page, how empty/loading states behave, what the primary action is.

## Step 3 — Write the files (this is the deliverable)

Produce real files, placed correctly, following Spendly's conventions:

- **New page** → a new `templates/<page>.html` that `{% extends "base.html" %}` and fills the content block. Don't duplicate the nav/header/footer that base.html already provides.
- **Page styles** → a **separate** `static/css/<page>.css`. Do **not** put styles in inline `<style>` blocks or `style=""` attributes. Link the file the same way base.html does — via `{% block extra_css %}` (or whatever the base uses), using `url_for('static', filename='css/<page>.css')`.
- **Every internal link and asset uses `url_for()`** — routes with `url_for('route_name')`, static files with `url_for('static', filename='...')`. Never hardcode a path like `/static/css/...` or `/add-expense`; hardcoded URLs break when routes move and are explicitly discouraged in this project.
- **Any interactivity is vanilla JS**, added to `static/js/main.js` or a page script loaded via the base's JS block. No frameworks, no CDN JS libraries.

Keep the markup semantic and the CSS lean — group related rules, use the project's spacing rhythm, and don't ship dead styles.

## Step 4 — Icons

Use **inline SVG** icons, since no icon package can be installed. Lucide and Heroicons publish plain SVG markup that pastes directly into templates and inherits color via `currentColor` — this keeps the clean, consistent fintech look without adding a dependency.

`references/icons.md` has ready-to-paste SVGs for the icons Spendly needs most (wallet, add, categories, calendar, charts, up/down trends, edit, delete, filter, search, settings). Read it and reuse those rather than re-deriving SVG paths each time. Pick icons that *mean* something in context — a trending-down arrow on a "spending decreased" stat, a wallet on balance, a tag on category — not decoration.

## Design language

Aim for a modern SaaS / fintech feel: calm, uncluttered, and trustworthy. Concretely:

- **Card-based layout.** Group content into cards with generous internal padding, subtle borders or soft shadows, and rounded corners. Cards are the primary organizing unit for dashboards, summaries, and forms.
- **8px spacing grid.** Use multiples of 8 (occasionally 4 for fine adjustments) for padding, margins, and gaps so everything lines up on a consistent rhythm.
- **Soft shadows, rounded corners.** Prefer low, diffuse shadows over hard ones; rounded corners (match the radius the project already uses).
- **Restrained color.** Mostly neutral surfaces and text, with the brand/accent color reserved for primary actions, key figures, and highlights. Use green/red intentionally for income/expense or up/down deltas — and don't rely on color alone (pair with an icon or label).
- **Clear hierarchy.** Establish a type scale (large numbers for headline figures, medium for section titles, small for labels/meta). Amounts are the hero content of an expense tracker — make the numbers legible and prominent.
- **Real states.** Design the empty state (no transactions yet), and hover/focus states for interactive elements. Forms get clear labels and visible focus rings for accessibility.
- **Responsive.** Layouts should hold up from mobile to desktop — stat rows wrap, tables become scrollable or restack, nothing overflows.

## Output format

Respond in this order:

1. **A brief plan** (Step 2) — layout, key sections, notable UX decisions. A few lines.
2. **The files**, written to their correct paths (template + CSS, plus any JS). Present them so the user can see what was created and where.
3. **A short explanation** — what you built and, importantly, *how it stays consistent with the existing design* (which tokens/classes you reused) and any assumptions you made (e.g. expected route names or data fields) that the user should verify.

Keep prose minimal around the code. The value is the working files, not a wall of commentary.

## Consistency & things to avoid

- **Match the existing design** derived in Step 1 — reuse its tokens, classes, and layout patterns. When something is ambiguous, prefer what's already in the project over your own preference. If you truly can't tell, ask for screenshots of the current UI.
- **Avoid a generic/dated look** — no default browser styling, no heavy borders everywhere, no clip-art gradients. This should read as a considered 2020s SaaS product.
- **Avoid unstructured code dumps** — files go to their proper paths with proper conventions, not a single blob of mixed HTML/CSS pasted into chat.
- **Don't break the conventions** — no inline styles, no hardcoded URLs, no new dependencies, no framework code.

## Worked example (abbreviated)

**User:** "Design the dashboard page — show total balance, this month's spending, and recent transactions."

**Good response shape:**

> **Plan:** Top row = three stat cards (Balance, Spent this month, Income this month) with trend deltas. Below = a "Recent transactions" card with a compact list and a "View all" link; primary "Add expense" button lives top-right of the header. Empty state shown when there are no transactions yet.

Then writes `templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}Dashboard · Spendly{% endblock %}
{% block extra_css %}
  <link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
{% endblock %}
{% block content %}
<section class="dashboard">
  <header class="dashboard__header">
    <h1>Overview</h1>
    <a class="btn btn--primary" href="{{ url_for('add_expense') }}">
      <!-- inline plus icon from references/icons.md -->
      Add expense
    </a>
  </header>
  <div class="stat-grid">
    <article class="card stat">
      <span class="stat__label">Balance</span>
      <span class="stat__value">{{ balance }}</span>
    </article>
    <!-- ...more stat cards... -->
  </div>
  <!-- ...recent transactions card, with empty state... -->
</section>
{% endblock %}
```

...and `static/css/dashboard.css` with card, stat-grid, and empty-state styles built on the tokens read from `style.css` — then a two-line note on which existing classes were reused and which route/field names to confirm.

(Block names, class names, and route names above are illustrative — use the ones you actually find in the project.)
