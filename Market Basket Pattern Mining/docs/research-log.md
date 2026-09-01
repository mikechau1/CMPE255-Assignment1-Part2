# Research Log

## Association-rule foundations

- Agrawal and Srikant define association rules as implications between disjoint item sets and introduce Apriori-family algorithms for efficient frequent-itemset and rule mining: [Fast Algorithms for Mining Association Rules in Large Databases](https://rsrikant.com/papers/vldb94.pdf).
- Han, Pei, Yin, and Mao describe FP-Growth as a frequent-pattern-tree method that compresses the database and avoids costly candidate generation: [Mining Frequent Patterns without Candidate Generation](https://www.cs.sfu.ca/~jpei/publications/dami03_fpgrowth.pdf).

## Dataset provenance

- Dataset source: [Groceries Market Basket Dataset on Kaggle](https://www.kaggle.com/datasets/irfanasrullah/groceries). The project records the source URL in every artifact and does not claim fields that are not present in the source.
- Observed-price deployment source: [Online Retail Dataset on Kaggle](https://www.kaggle.com/datasets/luisrenterialezano/retail-sales-dataset), an MIT-licensed CSV conversion of the [UCI Online Retail dataset](https://archive.ics.uci.edu/dataset/352/online+retail). Its invoice, quantity, and unit-price fields support basket formation and GBP GMV. Cancellations, returns, missing descriptions, and non-positive prices are excluded; cart prices use the median observed positive unit price per normalized product.

## Research-to-dashboard mapping

| Research concept | Dashboard treatment |
|---|---|
| Frequent itemset support | Frequent-itemset and KPI views |
| Rule confidence | Rule table and ranking filter |
| Lift | Hero metric, rule ranking, network edge option |
| Candidate-generation efficiency | Algorithm/runtime comparison |
| Reproducibility | Dataset hash, seed, configuration, and trial ledger |
