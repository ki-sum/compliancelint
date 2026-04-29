# ComplianceLint Public Docs Site

Docusaurus-based public user manual for ComplianceLint. Renders to
**docs.compliancelint.dev** (domain pending).

## Architecture

This is the **scaffold + theming + sidebar** layer. The actual chapter
content (MDX files) and walkthrough screenshots are **generated** by an
upstream pipeline owned by the maintainers and **not committed** here.

The scaffold + theme + sidebar live in this repo. The generated MDX
chapters and screenshot assets land under:

- `docs-site/docs/` — gitignored, populated at build time
- `docs-site/static/img/walkthrough/` — gitignored, populated at build time

If you only have this repo, the scaffold and theming layer are fully
visible (config, sidebar, src/, static/). To preview the rendered
content, deploy via CI or wait for the live site.

## Local development

Prereq: the upstream sync must have run at least once to populate
`docs/` and `static/img/walkthrough/`.

```bash
cd docs-site
npm install
npm start -- --port 3001    # the dashboard owns :3000
```

If `docs/` is empty (no sync has run), the dev server will start but
render no chapters. Maintainers run the sync from the upstream
dashboard repo's scripts.

## Build

```bash
npm run build
npm run serve   # serve the production build at :3000
```

## Deploy

Deployment platform TBD. Likely candidates: Cloudflare Pages, Vercel,
GitHub Pages. The CI flow will be:

1. Clone repos + run upstream sync
2. `cd docs-site && npm install && npm run build`
3. Deploy `docs-site/build/` static output

## Contributing

The MDX chapters are auto-generated — **do not edit them directly here**.
For content changes, raise an issue or PR against the upstream repo.

For scaffold / theme / sidebar changes (this repo), normal PR flow
applies.

## License

ComplianceLint is open-source under [BSL 1.1](../LICENSE).
