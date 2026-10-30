# Portfolio repository

This repository contains Chirag Batra's static AI engineering portfolio. The deployed site is the React/Vite app in `frontend/`; GitHub Pages builds it from `frontend/dist/`.

## Keep

- Portfolio pages and shared UI in `frontend/src/`.
- Résumé and project content in `frontend/src/data/` and static assets in `frontend/public/`.
- The browser-based Churn Uplift Lab and its model training/export source in `ml/churn/`.
- The local-only project editor in `frontend/plugins/projectEditor.ts`.
- The GitHub Pages deploy workflow and frontend CI.

There is no portfolio backend. Keep runtime pages static and make interactive demos work in the browser.

## Development

```sh
cd frontend
npm ci
npm run dev
npm run lint
npm test
npm run build
```

Pushes to `main` deploy the production build through `.github/workflows/frontend-deploy.yml`. For repository project pages, the production Vite base is `/chirag_batra_portfolio/`.

The Churn Lab model is exported to `frontend/public/models/churn-lab.json`; training and model tests live in `ml/churn/`.

Do not commit secrets. `GITHUB_TOKEN` is optional and only used by the local project editor to look up public repository details.
