# Chirag Batra · AI Engineer Portfolio

Personal portfolio and résumé site for my work in machine learning, data science, and applied AI.

**[View the portfolio](https://thechiragbatra.github.io/deploysmith/)** · [Résumé PDF](https://thechiragbatra.github.io/deploysmith/resume.pdf) · [GitHub](https://github.com/thechiragbatra) · [LinkedIn](https://www.linkedin.com/in/chirag-batra-ds)

Built with React, TypeScript, Vite, and Tailwind CSS. The site is a static GitHub Pages deployment; the portfolio and interactive Churn Uplift Lab run without a backend.

## Featured work

| Project | What I worked on | Results / status |
| --- | --- | --- |
| **EventLens AI** · IBM internship | Financial risk analytics combining GDELT news signals with live market data, a Random Forest model, VaR and Monte Carlo projections, FastAPI, and a React dashboard. | 250+ event-days used for model training. |
| **[Hireloop: AI Job Copilot](https://github.com/thechiragbatra/hireloop)** | Resume-grounded job matching with hybrid retrieval, a LangGraph workflow, human review, and a faithfulness verifier. | In progress. |
| **[Customer Churn MLOps](https://github.com/thechiragbatra/customer-churn-mlops)** | XGBoost churn prediction, T-learner uplift segments, SHAP explanations, and a FastAPI/Streamlit app. | 0.82 AUC-ROC; 56% lower simulated campaign spend. |
| **[Proactive Academic Intervention System](https://github.com/thechiragbatra/proactive-academic-intervention-system)** | Team-built student-risk app with a hybrid model, feature engineering, and six DSA modules. | 0.887 ROC-AUC, 0.764 F1, 79.9% recall. |

The portfolio includes project write-ups, a résumé view with a PDF download, and an interactive churn model that runs in the browser.

## Run locally

Requirements: Node.js 22 or newer.

```sh
cd frontend
npm install
npm run dev
```

Create and preview a production build:

```sh
npm run build
npm run preview
```

Portfolio content lives in `frontend/src/data/`. Project visuals and the downloadable résumé are in `frontend/public/`.

## GitHub Pages deployment

The workflow at [`.github/workflows/frontend-deploy.yml`](.github/workflows/frontend-deploy.yml) builds `frontend/` and deploys `frontend/dist/` to GitHub Pages on every push to `main`. Set the repository’s Pages source to **GitHub Actions**. The production build uses the `/deploysmith/` project-site path.

## Contact

- Email: [batrachirag748@gmail.com](mailto:batrachirag748@gmail.com)
- LinkedIn: [chirag-batra-ds](https://www.linkedin.com/in/chirag-batra-ds)
- GitHub: [thechiragbatra](https://github.com/thechiragbatra)
