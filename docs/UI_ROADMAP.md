# UI / design roadmap

Current: Fusion + light/dark theme, expandable sidebar nav, maximized by default.

## Phase 1 — Quick polish — done

- Blue-gray palette; primary on form actions only
- **Reminders** header button — soft red; other header actions neutral
- Text-only nav (no icons)
- Page title + subtitle on every screen (`src/ui/page_header.py`)

## Phase 2 — Information hierarchy — done

- Dashboard cards: color only for “needs attention” (overdue, due today, low stock)
- Empty states on main data tables (`src/ui/table_empty.py`)

## Phase 3 — Power user — done

- Expandable nav groups (Overview, Sales, Stock, Administration) via `QTreeWidget`
- Dark mode toggle in the **header** (next to search)
- App opens **maximized** by default

## Phase 4 — Design system refresh — done

- Muted indigo accent (`#5b5bd6`) aligned with desktop + web (Stripe / Linear style)
- Soft nav selection (tinted background, not solid fill)
- Sidebar brand + refined search field; login uses theme tokens
- Web: CSS variables, `prefers-color-scheme` dark, KPI alert cards, brand mark

## Phase 6 — Forms & table actions — done

- Form labels: transparent text (no Fusion gray label-column fill); `form_util.py`
- Trash / Restore: flat `btnIconDanger`, centered in `tableActionCell`; shared `table_action.py`
- Seed / Settings / Payments forms use `formCard` panels (solid bg, no nested shading)

## Phase 5 — Nav polish — done

- Brand block uses layout (no negative QSS margin → subtitle no longer clipped)
- Tree selection: `show-decoration-selected: 0`, transparent branches, palette synced to accent tokens

## Future ideas (inspired by modern dashboard UIs)

| Idea | Why |
|------|-----|
| **Sidebar icons** (thin line, 16px) | Faster scan — Figma/Stripe pattern; keep text labels |
| **Reminder badge** on nav / header | Red dot or count on “Due / Outstanding” when overdue > 0 |
| **Dashboard mini-charts** | Sparkline on MTD sales / collections cards (reference boards) |
| **Sticky page toolbar** | Filter + primary action stay visible while scrolling long tables |
| **Icon-only collapsed nav** | ☰ toggles 252px → 56px rail for data-heavy screens |
| **Table row hover + zebra** | Already partial — unify across Invoices, Payments, Due |
| **System theme sync** | Follow Windows light/dark automatically |
| **Web theme toggle** | Match desktop `ui_dark_mode` setting |

- Remember window size when user un-maximizes
