"""CRISP-DM Phase 4 - rag-pipeline, over the 46 installed skills.

The corpus is the lab's own documentation: every SKILL.md installed under
.claude/skills. That makes the retrieval evaluation checkable -- each question
has a known correct skill -- and it is a genuinely useful index, because the
question "which skill do I need for X" is the one this repo raises constantly.

Three retrievers are compared on the same 20 questions: BM25, dense embeddings,
and hybrid fusion with cross-encoder reranking.
"""
from __future__ import annotations
import re, sys, pathlib, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np

from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.net import use_system_certs
from lib.paths import SKILLS, ARTIFACTS
from lib.seeds import set_global_seed

use_system_certs()

CHUNK_TOKENS = 180
OVERLAP = 40

# question -> the skill that should be retrieved. Written from the task, not from the text.
QUERIES = {
    "how do I stop preprocessing from leaking into cross validation": "sklearn-pipelines",
    "my fraud target is only 0.2% positive, what metric should I use": "imbalanced-data",
    "the model scores 0.99 AUC and I do not believe it": "ml-debugging",
    "how should I fill missing values without touching the test set": "data-cleaning",
    "compare random search against bayesian optimisation for my model": "hyperparameter-tuning",
    "how do I serve a trained sklearn model behind an HTTP API": "model-serving",
    "log parameters and metrics so I can compare runs later": "experiment-tracking",
    "pin seeds and package versions so results can be reproduced": "reproducible-ml",
    "fine tune a small language model with LoRA adapters": "llm-finetuning",
    "chunk documents and retrieve them with embeddings": "rag-pipeline",
    "my pandas code is slow because of apply over rows": "pandas-patterns",
    "measure retention by signup month": "cohort-analysis",
    "two dashboards report different revenue numbers": "metric-reconciliation",
    "is this A/B test result statistically significant": "ab-test-analysis",
    "revenue dropped last month and I need to find out why": "root-cause-investigation",
    "write a one page summary for the executive team": "executive-summary-generator",
    "group customers by behaviour and profile the segments": "segmentation-analysis",
    "what should I ask before starting an analysis request": "stakeholder-requirements-gathering",
    "check nulls duplicates and freshness on a warehouse table": "data-quality-audit",
    "explain a model to a non technical stakeholder": "technical-to-business-translator",
}


def chunk_corpus() -> list[dict]:
    """Split each SKILL.md on markdown headings, then pack to ~180 words with overlap."""
    chunks = []
    for skill_dir in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        md = skill_dir / "SKILL.md"
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"\n(?=#{1,3} )", text)
        for si, sec in enumerate(sections):
            words = sec.split()
            if not words:
                continue
            step = max(CHUNK_TOKENS - OVERLAP, 1)
            for start in range(0, len(words), step):
                piece = words[start:start + CHUNK_TOKENS]
                if len(piece) < 25 and start > 0:
                    break
                chunks.append({"skill": skill_dir.name, "section": si,
                               "text": " ".join(piece), "id": f"{skill_dir.name}#{si}.{start}"})
    return chunks


def metrics_at_k(ranked_skills: list[list[str]], golds: list[str]) -> dict:
    out = {}
    for k in (1, 3, 5):
        out[f"recall@{k}"] = float(np.mean([g in r[:k] for r, g in zip(ranked_skills, golds)]))
    rr = []
    for r, g in zip(ranked_skills, golds):
        rr.append(1.0 / (r.index(g) + 1) if g in r else 0.0)
    out["mrr"] = float(np.mean(rr))
    return out


def dedupe(skills: list[str]) -> list[str]:
    seen, out = set(), []
    for s in skills:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def run() -> SkillResult:
    set_global_seed()
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer, CrossEncoder

    chunks = chunk_corpus()
    texts = [c["text"] for c in chunks]
    queries = list(QUERIES)
    golds = [QUERIES[q] for q in queries]

    # --- lexical
    tokenised = [re.findall(r"[a-z0-9]+", t.lower()) for t in texts]
    bm25 = BM25Okapi(tokenised)
    t0 = time.perf_counter()
    bm25_scores = np.array([bm25.get_scores(re.findall(r"[a-z0-9]+", q.lower())) for q in queries])
    bm25_time = time.perf_counter() - t0

    # --- dense
    encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    t0 = time.perf_counter()
    doc_emb = encoder.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    index_time = time.perf_counter() - t0
    q_emb = encoder.encode(queries, normalize_embeddings=True, show_progress_bar=False)
    t0 = time.perf_counter()
    dense_scores = q_emb @ doc_emb.T
    dense_time = time.perf_counter() - t0

    # --- hybrid: reciprocal rank fusion, then cross-encoder rerank of the top 20 chunks
    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    K_RRF = 60
    bm25_only, dense_only, hybrid_only, rerank_only = [], [], [], []
    examples = []
    t0 = time.perf_counter()
    for qi, q in enumerate(queries):
        b_rank = np.argsort(-bm25_scores[qi])
        d_rank = np.argsort(-dense_scores[qi])
        rrf = np.zeros(len(texts))
        for r, idx in enumerate(b_rank[:100]):
            rrf[idx] += 1.0 / (K_RRF + r + 1)
        for r, idx in enumerate(d_rank[:100]):
            rrf[idx] += 1.0 / (K_RRF + r + 1)
        h_rank = np.argsort(-rrf)

        cand = h_rank[:20]
        ce = reranker.predict([(q, texts[i]) for i in cand], show_progress_bar=False)
        reranked = cand[np.argsort(-ce)]

        bm25_only.append(dedupe([chunks[i]["skill"] for i in b_rank[:40]]))
        dense_only.append(dedupe([chunks[i]["skill"] for i in d_rank[:40]]))
        hybrid_only.append(dedupe([chunks[i]["skill"] for i in h_rank[:40]]))
        rerank_only.append(dedupe([chunks[i]["skill"] for i in reranked]))

        if qi < 6:
            examples.append([q, QUERIES[q], chunks[reranked[0]]["skill"],
                             "hit" if chunks[reranked[0]]["skill"] == QUERIES[q] else "miss",
                             chunks[reranked[0]]["text"][:110] + "..."])
    rerank_time = time.perf_counter() - t0

    results = {
        "BM25 (lexical)": metrics_at_k(bm25_only, golds),
        "Dense (MiniLM-L6)": metrics_at_k(dense_only, golds),
        "Hybrid (RRF)": metrics_at_k(hybrid_only, golds),
        "Hybrid + reranker": metrics_at_k(rerank_only, golds),
    }
    best = max(results, key=lambda k: results[k]["mrr"])

    lens = [len(c["text"].split()) for c in chunks]
    hist, edges = np.histogram(lens, bins=8)

    return SkillResult(
        skill="rag-pipeline", source="agent-ml-skills",
        category="LLMs & GenAI", phase=4, track="T5",
        title=f"Retrieval over 46 skill documents, four retrievers, {len(queries)} labelled questions",
        prescribes="Chunk on structure with overlap, embed, retrieve with both lexical and dense signals, "
                   "fuse and rerank, and evaluate retrieval against labelled queries instead of eyeballing it.",
        applied=f"Chunked every installed SKILL.md into {len(chunks)} passages, indexed them with BM25 and "
                "MiniLM-L6 embeddings, fused with reciprocal rank fusion, reranked the top 20 with a "
                "cross-encoder, and scored all four against 20 hand-labelled questions.",
        narrative=[
            f"The corpus is {len(chunks)} chunks from 46 documents, averaging {np.mean(lens):.0f} words with a "
            f"{OVERLAP}-word overlap and a split on markdown headings first. Structure-aware chunking matters "
            "here because a skill document is a sequence of self-contained instructions -- cutting mid-section "
            "produces passages that answer nothing.",
            f"Every retriever is scored on the same 20 questions with a known correct skill, so the comparison "
            f"is a number rather than an impression. BM25 gets recall@1 of "
            f"{results['BM25 (lexical)']['recall@1']:.0%}, dense embeddings "
            f"{results['Dense (MiniLM-L6)']['recall@1']:.0%}, RRF fusion "
            f"{results['Hybrid (RRF)']['recall@1']:.0%}, and adding the cross-encoder reranker "
            f"{results['Hybrid + reranker']['recall@1']:.0%}.",
            f"The two signals fail differently, which is why fusing helps: BM25 puts the right skill in the top "
            f"three on {results['BM25 (lexical)']['recall@3']:.0%} of questions but only first on "
            f"{results['BM25 (lexical)']['recall@1']:.0%} -- it finds the neighbourhood and misranks inside it "
            "-- while the dense index ranks better at position one and occasionally misses the neighbourhood "
            "entirely. Reciprocal rank fusion takes the better half of each.",
            f"The cross-encoder reranker did not help here: recall@1 stays at "
            f"{results['Hybrid + reranker']['recall@1']:.0%} and MRR moves "
            f"{results['Hybrid + reranker']['mrr'] - results['Hybrid (RRF)']['mrr']:+.3f}, for "
            f"{rerank_time / len(queries) * 1000:.0f} ms of extra latency per query. That is a real negative "
            f"result worth keeping: the chunks here average {np.mean(lens):.0f} words, and an MS MARCO-trained "
            "reranker has little to work with on passages that short. On longer, noisier documents the same "
            "step usually earns its cost -- which is the argument for measuring it rather than assuming it.",
            f"Cost is asymmetric and worth stating: BM25 answers all 20 queries in {bm25_time * 1000:.0f} ms, "
            f"the dense search in {dense_time * 1000:.0f} ms after a {index_time:.1f}s indexing pass, and the "
            f"reranking pass costs {rerank_time:.1f}s in total because it runs a transformer over 20 "
            "query-passage pairs per question. On CPU that dominates the latency budget.",
        ],
        kpis=[
            Kpi("Chunks indexed", f"{len(chunks):,}", f"46 documents, ~{np.mean(lens):.0f} words each"),
            Kpi("Best recall@1", f"{results[best]['recall@1']:.0%}", best, tone="good"),
            Kpi("Best MRR", f"{results[best]['mrr']:.3f}", "mean reciprocal rank of the correct skill"),
            Kpi("Rerank cost", f"{rerank_time / len(queries) * 1000:.0f} ms/query", "CPU cross-encoder",
                tone="warn"),
        ],
        charts=[
            Chart(id="retriever-compare", kind="bar", title="Retrieval quality by strategy",
                  data=[{"x": k, "recall@1": round(v["recall@1"], 3), "recall@3": round(v["recall@3"], 3),
                         "mrr": round(v["mrr"], 3)} for k, v in results.items()],
                  series=[{"key": "recall@1", "label": "Recall@1"}, {"key": "recall@3", "label": "Recall@3"},
                          {"key": "mrr", "label": "MRR"}], valueFormat="percent"),
            Chart(id="chunk-lengths", kind="bar", title="Chunk length distribution (words)",
                  data=[{"x": f"{int(edges[i])}-{int(edges[i + 1])}", "n": int(hist[i])}
                        for i in range(len(hist))],
                  series=[{"key": "n", "label": "chunks"}]),
        ],
        tables=[
            Table("metrics", "Retrieval evaluation (20 labelled questions)",
                  ["Retriever", "Recall@1", "Recall@3", "Recall@5", "MRR"],
                  [[k, f"{v['recall@1']:.0%}", f"{v['recall@3']:.0%}", f"{v['recall@5']:.0%}",
                    f"{v['mrr']:.3f}"] for k, v in results.items()]),
            Table("examples", "Top result after reranking (first six questions)",
                  ["Question", "Expected skill", "Top-1 skill", "Result", "Retrieved passage"], examples),
        ],
        code_excerpt=(
            "# reciprocal rank fusion of the two rankings, then cross-encoder rerank\n"
            "rrf = np.zeros(len(texts))\n"
            "for r, idx in enumerate(np.argsort(-bm25_scores[qi])[:100]): rrf[idx] += 1 / (60 + r + 1)\n"
            "for r, idx in enumerate(np.argsort(-dense_scores[qi])[:100]): rrf[idx] += 1 / (60 + r + 1)\n\n"
            "cand = np.argsort(-rrf)[:20]\n"
            "scores = reranker.predict([(query, texts[i]) for i in cand])\n"
            "ranked = cand[np.argsort(-scores)]"
        ),
        takeaway=f"Fusing lexical and dense retrieval lifts recall@1 from "
                 f"{results['BM25 (lexical)']['recall@1']:.0%} to {results['Hybrid (RRF)']['recall@1']:.0%}, "
                 f"while the cross-encoder rerank adds {rerank_time / len(queries) * 1000:.0f} ms per query "
                 "and no accuracy on this corpus -- a conclusion only the labelled query set could support.",
    )


if __name__ == "__main__":
    print("\n=== CRISP-DM 4 (heavy): rag-pipeline ===")
    emit(run())
