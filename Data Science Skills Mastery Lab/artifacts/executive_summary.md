# Churn retention model -- executive summary

**Recommendation: fund a monthly retention campaign on the model's top three deciles, and
resolve one data question before the first send.**

**Why now.** $139,131 of monthly recurring revenue sits with
customers who churn, $1,669,570 annualised. Churn is
26.5% of the base and 87% of the exposure is in
month-to-month contracts, which are the easiest to convert.

**What we built.** A gradient-boosted model scoring every customer monthly. It ranks at 0.8526 ROC-AUC;
the top decile churns at 2.8x the base rate. It is calibrated, so its probabilities can be multiplied by money.

**What it is worth.** At the value-maximising threshold the campaign nets $122,606 on the held-out test split,
about $612,855 scaled to the full customer book -- published as a range of
$94,362 - $251,631 because four of its five inputs are business assumptions,
not measurements.

**What we need from you.**
1. Confirm the churn observation window with the data owner (blocking -- the target definition depends on it).
2. Sign off the offer economics: a $100 expected cost per offer and a 30% save rate.
3. Approve a 50/50 holdout on the first campaign so the save rate stops being an assumption.

**What this does not cover.** Win-back of already-churned customers, pricing strategy, and network quality.
The retail analyses in this lab use a different dataset and do not describe these customers.
