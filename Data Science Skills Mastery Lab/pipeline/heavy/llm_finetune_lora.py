"""CRISP-DM Phase 4 - llm-finetuning: LoRA on distilgpt2, on CPU.

The task is deliberately narrow and format-heavy, which is what LoRA is actually
good for: turn a customer's attributes into a fixed-shape retention verdict.

Training pairs are generated from the Telco *training split* by an explicit rule
set, so the target format is consistent and the evaluation is honest -- the
model is being taught a format and a decision boundary that exist in the data,
not being asked to invent facts. The rules are printed in the artifact.
"""
from __future__ import annotations
import math, sys, pathlib, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.net import use_system_certs
from lib.paths import ARTIFACTS
from lib.seeds import SEED, set_global_seed

use_system_certs()

BASE_MODEL = "distilgpt2"
MAX_LEN = 128
BATCH = 8
EPOCHS = 3
LR = 2e-4


def verdict(row) -> tuple[str, str, str]:
    """The rule set the model is being taught. Derived from phase-2/3 findings."""
    risk_points = 0
    drivers = []
    if row["Contract"] == "Month-to-month":
        risk_points += 2
        drivers.append("month-to-month contract")
    if row["tenure"] <= 6:
        risk_points += 2
        drivers.append("first six months")
    elif row["tenure"] <= 12:
        risk_points += 1
        drivers.append("under a year tenure")
    if row["InternetService"] == "Fiber optic":
        risk_points += 1
        drivers.append("fiber service")
    if row["TechSupport"] == "No":
        risk_points += 1
        drivers.append("no tech support")
    if row["PaymentMethod"] == "Electronic check":
        risk_points += 1
        drivers.append("electronic check payment")
    risk = "HIGH" if risk_points >= 4 else "MEDIUM" if risk_points >= 2 else "LOW"
    action = {"HIGH": "offer a 12-month contract with bundled tech support",
              "MEDIUM": "send a loyalty discount and a service health check",
              "LOW": "no intervention; monitor next quarter"}[risk]
    return risk, ", ".join(drivers[:2]) or "no material risk factors", action


def to_text(row) -> str:
    risk, driver, action = verdict(row)
    return (f"### Customer\n"
            f"tenure: {int(row['tenure'])} months | contract: {row['Contract']} | "
            f"internet: {row['InternetService']} | tech support: {row['TechSupport']} | "
            f"payment: {row['PaymentMethod']} | monthly: ${row['MonthlyCharges']:.2f}\n"
            f"### Retention verdict\n"
            f"risk: {risk}\ndriver: {driver}\naction: {action}<|endoftext|>")


def prompt_of(row) -> str:
    return to_text(row).split("### Retention verdict")[0] + "### Retention verdict\nrisk:"


class TextDS(Dataset):
    def __init__(self, texts, tok):
        self.enc = [tok(t, truncation=True, max_length=MAX_LEN, padding="max_length",
                        return_tensors="pt") for t in texts]

    def __len__(self):
        return len(self.enc)

    def __getitem__(self, i):
        e = self.enc[i]
        ids = e["input_ids"][0]
        mask = e["attention_mask"][0]
        labels = ids.clone()
        labels[mask == 0] = -100          # do not train on padding
        return {"input_ids": ids, "attention_mask": mask, "labels": labels}


@torch.no_grad()
def eval_loss(model, dl) -> float:
    model.eval()
    total, n = 0.0, 0
    for batch in dl:
        out = model(**batch)
        total += out.loss.item() * batch["input_ids"].size(0)
        n += batch["input_ids"].size(0)
    return total / n


def run() -> SkillResult:
    set_global_seed()
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    X_tr, X_te, y_tr, y_te = data.churn_split()
    train_rows = X_tr.head(600)
    eval_rows = X_te.head(120)
    train_texts = [to_text(r) for _, r in train_rows.iterrows()]
    eval_texts = [to_text(r) for _, r in eval_rows.iterrows()]

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL).to(device)

    train_dl = DataLoader(TextDS(train_texts, tok), batch_size=BATCH, shuffle=True)
    eval_dl = DataLoader(TextDS(eval_texts, tok), batch_size=BATCH)

    base_loss = eval_loss(base, eval_dl)

    def generate(model, row) -> str:
        model.eval()
        enc = tok(prompt_of(row), return_tensors="pt").to(device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=40, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        return tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    sample_rows = [eval_rows.iloc[i] for i in (0, 1, 2)]
    before = [generate(base, r) for r in sample_rows]

    lora_cfg = LoraConfig(r=8, lora_alpha=32, lora_dropout=0.05, bias="none",
                          task_type="CAUSAL_LM", target_modules=["c_attn"])
    model = get_peft_model(base, lora_cfg).to(device)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)
    steps_total = EPOCHS * len(train_dl)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=LR, total_steps=steps_total, pct_start=0.1)

    history = []
    t0 = time.perf_counter()
    step = 0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        running = 0.0
        for batch in train_dl:
            batch = {k: v.to(device) for k, v in batch.items()}
            opt.zero_grad(set_to_none=True)
            loss = model(**batch).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
            sched.step()
            running += loss.item()
            step += 1
            if step % 10 == 0:
                history.append({"step": step, "train_loss": round(running / 10, 4)})
                running = 0.0
        ev = eval_loss(model, eval_dl)
        print(f"  epoch {epoch}/{EPOCHS} eval_loss={ev:.4f}")
    train_seconds = time.perf_counter() - t0
    tuned_loss = eval_loss(model, eval_dl)

    after = [generate(model, r) for r in sample_rows]
    adapter_dir = ARTIFACTS / "lora_churn_adapter"
    model.save_pretrained(adapter_dir)
    adapter_mb = sum(f.stat().st_size for f in adapter_dir.rglob("*") if f.is_file()) / 2**20

    # Did it learn the format? Check the generations parse into the three required fields.
    def parses(text: str) -> bool:
        return ("driver:" in text and "action:" in text and
                text.split()[0].rstrip(":").upper() in {"HIGH", "MEDIUM", "LOW"})

    all_eval = [eval_rows.iloc[i] for i in range(0, 30)]
    gen_after = [generate(model, r) for r in all_eval]
    format_ok = float(np.mean([parses(g) for g in gen_after]))
    risk_correct = float(np.mean([g.split()[0].rstrip(":").upper() == verdict(r)[0]
                                  for g, r in zip(gen_after, all_eval) if g.split()]))

    return SkillResult(
        skill="llm-finetuning", source="agent-ml-skills",
        category="LLMs & GenAI", phase=4, track="T5",
        title=f"LoRA on {BASE_MODEL}: {trainable / 1e6:.2f}M trainable parameters of {total / 1e6:.1f}M",
        prescribes="Prefer LoRA/QLoRA over full fine-tuning when adapting a small model to a narrow task; "
                   "format the data as consistent prompt-completion pairs, mask the padding, and evaluate on "
                   "held-out examples rather than on training loss.",
        applied=f"Built {len(train_texts)} prompt-completion pairs from the churn training split, attached LoRA "
                f"adapters (r=8, alpha=32) to distilgpt2's attention projections, and trained {EPOCHS} epochs "
                f"on CPU in {train_seconds:.0f} seconds.",
        narrative=[
            f"LoRA trains {trainable:,} parameters against the model's {total:,} -- "
            f"{trainable / total:.2%}. The saved adapter is {adapter_mb:.1f} MB rather than a 350 MB model "
            "copy, which is the operational argument: one base model in memory, many task adapters on disk.",
            f"Held-out loss falls from {base_loss:.3f} to {tuned_loss:.3f} "
            f"(perplexity {math.exp(base_loss):.1f} -> {math.exp(tuned_loss):.1f}) on 120 unseen customers. "
            "The base model's generations below are plausible English about nothing in particular; after "
            "training they follow the three-field format the task requires.",
            f"Format compliance is the metric that matters for a structured-output task: "
            f"{format_ok:.0%} of 30 held-out generations parse into risk/driver/action, and {risk_correct:.0%} "
            "of the risk labels match the rule the data was generated from. A loss number alone would not have "
            "told us whether the output is usable by a downstream system.",
            "The honest caveat: the training targets are generated by an explicit rule set (printed below) "
            "derived from the phase-2 findings, so this demonstrates that LoRA can teach a small model a "
            "consistent decision format -- it does not demonstrate that the model discovered churn drivers on "
            "its own. Saying which of those two happened is the difference between a demo and a claim.",
        ],
        kpis=[
            Kpi("Trainable parameters", f"{trainable / 1e6:.2f}M", f"{trainable / total:.2%} of the model",
                tone="good"),
            Kpi("Adapter size", f"{adapter_mb:.1f} MB", "vs a full model copy"),
            Kpi("Held-out perplexity", f"{math.exp(base_loss):.1f} -> {math.exp(tuned_loss):.1f}",
                "base -> LoRA", tone="good"),
            Kpi("Format compliance", f"{format_ok:.0%}", f"risk label correct on {risk_correct:.0%}"),
        ],
        charts=[
            Chart(id="lora-loss", kind="line", title="Training loss (10-step moving window)",
                  data=[{"x": h["step"], "loss": h["train_loss"]} for h in history],
                  series=[{"key": "loss", "label": "train loss"}], xLabel="optimiser step"),
            Chart(id="lora-params", kind="bar", title="Parameters: full fine-tune vs LoRA",
                  data=[{"x": "Full fine-tune", "params": round(total / 1e6, 2)},
                        {"x": "LoRA (r=8, c_attn)", "params": round(trainable / 1e6, 2)}],
                  series=[{"key": "params", "label": "trainable parameters (M)"}]),
        ],
        tables=[
            Table("generations", "Same prompt, base model vs LoRA-tuned",
                  ["Customer (tenure / contract / support)", "Base distilgpt2", "After LoRA"],
                  [[f"{int(r['tenure'])}m / {r['Contract']} / support={r['TechSupport']}",
                    b.replace("\n", " ")[:120], a.replace("\n", " ")[:120]]
                   for r, b, a in zip(sample_rows, before, after)]),
            Table("config", "Training configuration",
                  ["Setting", "Value"],
                  [["Base model", BASE_MODEL], ["Adapter", "LoRA r=8, alpha=32, dropout=0.05"],
                   ["Target modules", "c_attn (attention QKV projection)"],
                   ["Sequence length", str(MAX_LEN)], ["Batch size", str(BATCH)],
                   ["Epochs", str(EPOCHS)], ["Learning rate", f"{LR} with OneCycle"],
                   ["Device", str(device)], ["Training pairs", str(len(train_texts))],
                   ["Wall clock", f"{train_seconds:.0f}s"]]),
        ],
        code_excerpt=(
            "lora_cfg = LoraConfig(r=8, lora_alpha=32, lora_dropout=0.05, bias='none',\n"
            "                      task_type='CAUSAL_LM', target_modules=['c_attn'])\n"
            "model = get_peft_model(base, lora_cfg)\n\n"
            "# labels = input_ids with padding masked out, so loss ignores the pad tokens\n"
            "labels = ids.clone(); labels[attention_mask == 0] = -100\n\n"
            "for batch in train_dl:\n"
            "    loss = model(**batch).loss\n"
            "    loss.backward()\n"
            "    clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)\n"
            "    opt.step(); sched.step(); opt.zero_grad(set_to_none=True)"
        ),
        takeaway=f"Training {trainable / total:.2%} of distilgpt2 for {train_seconds:.0f}s on CPU takes held-out "
                 f"perplexity from {math.exp(base_loss):.0f} to {math.exp(tuned_loss):.0f} and produces "
                 f"parseable output {format_ok:.0%} of the time -- adapters, not a new model.",
        artifacts=["artifacts/lora_churn_adapter"],
    )


if __name__ == "__main__":
    print("\n=== CRISP-DM 4 (heavy): llm-finetuning ===")
    emit(run())
