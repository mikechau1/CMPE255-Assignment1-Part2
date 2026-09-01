# Data Science Skills Mastery Lab -- analysis documentation

## Purpose
Demonstrate all 46 skills from two public Claude Code skill collections
(15 from param087/agent-ml-skills, 31
from nimrodfisher/data-analytics-skills) on popular Kaggle datasets, organised by the six CRISP-DM phases.

## Data
- telco_churn (blastchar/telco-customer-churn) sha256=16320c9c1ec7
- titanic (c/titanic) sha256=4a437fde05fe
- online_retail (vijayuv/onlineretail) sha256=f5385cbb54bb
- fashion_mnist_train_images (zalando-research/fashionmnist) sha256=3aede38d6186
- fashion_mnist_train_labels (zalando-research/fashionmnist) sha256=a04f17134ac0
- fashion_mnist_test_images (zalando-research/fashionmnist) sha256=346e55b948d9
- fashion_mnist_test_labels (zalando-research/fashionmnist) sha256=67da17c76eaf
- online_retail_csv (vijayuv/onlineretail) sha256=c820e928a9cb
- creditcard (mlg-ulb/creditcardfraud) sha256=5ac0db239c79

## Method
One Python pipeline (`pipeline/`), one module per CRISP-DM phase, plus `pipeline/heavy/` for the
deep-learning, LLM, retrieval and serving demos. Every demo returns a `SkillResult` and is serialised
to `site/public/artifacts/<skill>.json`; the React site renders those files and never runs Python.

## Reproduction
```
python pipeline/00_download_data.py
python pipeline/crisp01_business_understanding.py   # ... through crisp06
python pipeline/heavy/pytorch_fashion.py            # and the other heavy scripts
python pipeline/skills_registry.py --check          # fails unless all 46 artifacts exist
```
Seed 20255255; environment fingerprint recorded by the `reproducible-ml` artifact.

## Limitations
- The churn observation window is assumed, not confirmed (blocking; see the peer review).
- Offer economics (save rate, offer cost) are assumptions, not measurements.
- The five dataset tracks are unrelated to one another; findings do not transfer between them.
- Fashion-MNIST and the LoRA/RAG tracks demonstrate technique, not a business outcome.
