# graphify
- **graphify** (`~/.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

# Web design house rules (every website and project)
Never ship these. Check for them before calling any UI work done.

**Visual**
- No gradients of any kind, especially purple or purple-to-blue; no gradient text.
- No glassmorphism (frosted or blurred cards) and no grain or noise textures.
- No coloured left-border cards or list items.
- No pill-shaped buttons (fully rounded labels for status are fine; anything you press is not).
- No three icon boxes in a row as a section.
- No badge, kicker or eyebrow label above a headline.
- No low-contrast dark mode: text meets WCAG AA in both themes.
- Keep spacing on one scale; no one-off gaps.

**Type and icons**
- No Inter everywhere; no Space Grotesk with Instrument Serif; no serif italics for accent words.
- No emoji, and no text glyphs (arrows, ticks, triangles) used as icons; draw icons as SVG.
- Don't default to Lucide icons or untouched shadcn components; style or draw them for the project.

**Motion**
- No sections fading in on scroll, no over-the-top scroll animations, no cursor-following effects.
- Allowed exception (user's request): a page's one signature animation may wait until its element scrolls into view, then play once, so it isn't missed below the fold.
- Buttons never fade on hover; hover changes the fill or shadow instead.

**Copy and content**
- No em dashes in interface copy.
- No generic buzzwords (seamless, leverage, empower, unlock, cutting-edge, AI-powered...).
- No fake reviews, fake metrics, fake hero text, AI slop copy or AI slop photos, and no invented people or businesses.

**Before launch**
- Custom domain connected, favicon set, any "Made with AI" or builder tag removed.
- Privacy policy and terms pages linked from the site.
