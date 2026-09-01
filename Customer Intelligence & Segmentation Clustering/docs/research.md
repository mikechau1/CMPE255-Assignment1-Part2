# Research notes

## Methodology

This implementation follows **CRISP-DM 1.0**, the step-by-step data-mining guide produced by the CRISP-DM consortium. The project maps its business objective, data understanding, preparation, modeling, evaluation, and deployment outputs to the six CRISP-DM phases.

## Cluster validation

Rousseeuw's 1987 silhouette paper defines a graphical and numerical view of within-cluster cohesion versus nearest-cluster separation. The pipeline therefore reports mean silhouette and exposes cluster-level profiles rather than relying on a single elbow chart.

Scikit-learn's clustering guidance distinguishes internal validation, which is appropriate when no ground-truth labels exist, from supervised comparison metrics. This dataset has no authoritative segment labels, so the project reports silhouette, Davies–Bouldin, Calinski–Harabasz, stability, and business interpretability.

## Autonomous experimentation

The autoresearch loop adapts the modify → run → measure → keep/reject pattern described in Karpathy's autoresearch repository. For this clustering use case, each run mutates an explicit configuration and uses a bounded deterministic budget. The loop never changes the evaluation code while experiments are running, and every run is logged for auditability.

## Sources

- Chapman et al. (2000), CRISP-DM 1.0: https://nas.uhcl.edu/boetticher/ML_DataMining/CRISPWP-0800.pdf
- Rousseeuw (1987), Silhouettes: https://wis.kuleuven.be/stat/robust/papers/publications-1987/rousseeuw-silhouettes-jcam-sciencedirectopenarchiv.pdf/view
- scikit-learn metrics API: https://scikit-learn.org/stable/api/sklearn.metrics.html
- scikit-learn K-Means assumptions: https://scikit-learn.org/stable/auto_examples/cluster/plot_kmeans_assumptions.html
- Karpathy autoresearch pattern: https://github.com/karpathy/autoresearch/blob/master/program.md?plain=1
- Dataset provenance: https://www.kaggle.com/datasets/vjchoudhary7/customer-segmentation-tutorial-in-python
