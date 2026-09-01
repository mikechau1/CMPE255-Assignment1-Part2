"""CRISP-DM Phase 4 - pytorch-training-loop, on Fashion-MNIST.

A small CNN trained for real on CPU. The point of the skill is the shape of the
loop -- train/eval mode discipline, no_grad at evaluation, device handling,
AMP only where it helps, and checkpointing on validation improvement -- so the
loop is written out in full rather than delegated to a trainer class.
"""
from __future__ import annotations
import sys, pathlib, time, json

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS
from lib.seeds import SEED, set_global_seed

EPOCHS = 6
BATCH = 128


class SmallCNN(nn.Module):
    def __init__(self, n_classes: int = 10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.MaxPool2d(2), nn.Dropout(0.25),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.MaxPool2d(2), nn.Dropout(0.25),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(64 * 7 * 7, 128), nn.ReLU(),
                                  nn.Dropout(0.4), nn.Linear(128, n_classes))

    def forward(self, x):
        return self.head(self.features(x))


def run() -> SkillResult:
    set_global_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = device.type == "cuda"

    xtr, ytr, xte, yte = data.fashion_mnist(n_train=12_000, n_test=3_000)
    to_t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).float().unsqueeze(1) / 255.0
    train_ds = TensorDataset(to_t(xtr), torch.from_numpy(np.ascontiguousarray(ytr)).long())
    test_ds = TensorDataset(to_t(xte), torch.from_numpy(np.ascontiguousarray(yte)).long())
    train_dl = DataLoader(train_ds, batch_size=BATCH, shuffle=True, drop_last=False)
    test_dl = DataLoader(test_ds, batch_size=256, shuffle=False)

    model = SmallCNN().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)
    lossf = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    ckpt = ARTIFACTS / "fashion_cnn.pt"
    history, best_acc, best_epoch = [], 0.0, 0
    t_start = time.perf_counter()

    for epoch in range(1, EPOCHS + 1):
        model.train()                                   # dropout and batchnorm in training mode
        running, seen, correct = 0.0, 0, 0
        for xb, yb in train_dl:
            xb, yb = xb.to(device, non_blocking=True), yb.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device.type, enabled=use_amp):
                out = model(xb)
                loss = lossf(out, yb)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            running += loss.item() * yb.size(0)
            correct += (out.argmax(1) == yb).sum().item()
            seen += yb.size(0)
        train_loss, train_acc = running / seen, correct / seen

        model.eval()                                    # dropout off, batchnorm uses running stats
        vloss, vseen, vcorrect = 0.0, 0, 0
        with torch.no_grad():                           # no graph, no memory, no accidental updates
            for xb, yb in test_dl:
                xb, yb = xb.to(device), yb.to(device)
                out = model(xb)
                vloss += lossf(out, yb).item() * yb.size(0)
                vcorrect += (out.argmax(1) == yb).sum().item()
                vseen += yb.size(0)
        val_loss, val_acc = vloss / vseen, vcorrect / vseen
        sched.step()

        history.append({"epoch": epoch, "train_loss": round(train_loss, 4), "val_loss": round(val_loss, 4),
                        "train_acc": round(train_acc, 4), "val_acc": round(val_acc, 4),
                        "lr": round(sched.get_last_lr()[0], 6)})
        if val_acc > best_acc:                          # checkpoint on improvement only
            best_acc, best_epoch = val_acc, epoch
            torch.save({"epoch": epoch, "model_state": model.state_dict(),
                        "optimizer_state": opt.state_dict(), "val_acc": val_acc, "seed": SEED}, ckpt)
        print(f"  epoch {epoch}/{EPOCHS} train_loss={train_loss:.4f} val_acc={val_acc:.4f}")

    train_seconds = time.perf_counter() - t_start

    # Restore the best checkpoint, then evaluate once.
    state = torch.load(ckpt, map_location=device, weights_only=True)
    model.load_state_dict(state["model_state"])
    model.eval()
    preds, trues = [], []
    with torch.no_grad():
        for xb, yb in test_dl:
            preds.append(model(xb.to(device)).argmax(1).cpu().numpy())
            trues.append(yb.numpy())
    preds, trues = np.concatenate(preds), np.concatenate(trues)

    classes = data.FASHION_CLASSES
    cm = np.zeros((10, 10), dtype=int)
    for t, p in zip(trues, preds):
        cm[t, p] += 1
    per_class = cm.diagonal() / cm.sum(1)
    worst = int(np.argmin(per_class))
    confused_with = int(np.argsort(cm[worst])[-2]) if np.argmax(cm[worst]) == worst else int(np.argmax(cm[worst]))

    # The classic bug this skill exists to prevent, measured rather than described.
    model.train()
    with torch.no_grad():
        wrong_mode = np.concatenate([model(xb.to(device)).argmax(1).cpu().numpy() for xb, _ in test_dl])
    train_mode_acc = float((wrong_mode == trues).mean())
    model.eval()

    n_params = sum(p.numel() for p in model.parameters())

    return SkillResult(
        skill="pytorch-training-loop", source="agent-ml-skills",
        category="Modeling", phase=4, track="T4",
        title=f"A CNN trained on Fashion-MNIST in {train_seconds:.0f}s of CPU",
        prescribes="Write the loop explicitly: model.train() / model.eval() around each phase, torch.no_grad() "
                   "for evaluation, gradient clipping, a scheduler stepped once per epoch, AMP only on CUDA, "
                   "and checkpoints saved on validation improvement.",
        applied=f"Trained a {n_params / 1e6:.2f}M-parameter CNN for {EPOCHS} epochs on a 12,000-image "
                f"Fashion-MNIST subsample, evaluating on 3,000 held-out images each epoch.",
        narrative=[
            f"Best validation accuracy is {best_acc:.3%} at epoch {best_epoch}, reached in {train_seconds:.0f} "
            f"seconds on CPU (torch {torch.__version__} -- this is the CPU build, so AMP is disabled and the "
            "autocast/GradScaler path is present but inert; the same loop runs unchanged on CUDA).",
            f"The mode discipline is not decoration. Running the identical evaluation with the model left in "
            f"`train()` -- dropout active, batchnorm updating on test batches -- gives {train_mode_acc:.3%} "
            f"instead of {best_acc:.3%}. That is a {best_acc - train_mode_acc:+.3%} swing from one forgotten "
            "line, and nothing crashes to tell you.",
            f"Per-class accuracy exposes what the aggregate hides: {classes[worst]} is the weakest class at "
            f"{per_class[worst]:.1%}, and its errors go mostly to {classes[confused_with]}. Shirt/pullover/coat "
            "confusion is the known hard case in this dataset, not a bug in the loop.",
            "Checkpointing writes only when validation improves and stores the optimiser state and the seed "
            "alongside the weights, so training is resumable rather than merely restartable.",
        ],
        kpis=[
            Kpi("Best val accuracy", f"{best_acc:.2%}", f"epoch {best_epoch} of {EPOCHS}", tone="good"),
            Kpi("Train time", f"{train_seconds:.0f}s", f"CPU, {EPOCHS} epochs, 12k images"),
            Kpi("Parameters", f"{n_params / 1e6:.2f}M", "small CNN"),
            Kpi("Cost of forgetting eval()", f"{train_mode_acc:.2%}",
                f"{train_mode_acc - best_acc:+.2%} vs correct mode", tone="bad"),
        ],
        charts=[
            Chart(id="loss-curve", kind="line", title="Loss by epoch",
                  data=[{"x": h["epoch"], "train": h["train_loss"], "val": h["val_loss"]} for h in history],
                  series=[{"key": "train", "label": "Train loss"}, {"key": "val", "label": "Validation loss"}],
                  xLabel="epoch"),
            Chart(id="acc-curve", kind="line", title="Accuracy by epoch",
                  data=[{"x": h["epoch"], "train": h["train_acc"], "val": h["val_acc"]} for h in history],
                  series=[{"key": "train", "label": "Train accuracy"},
                          {"key": "val", "label": "Validation accuracy"}],
                  xLabel="epoch", valueFormat="percent"),
            Chart(id="confusion", kind="heatmap", title="Confusion matrix (best checkpoint, 3,000 test images)",
                  data=[{"row": classes[i], "col": classes[j], "value": int(cm[i, j])}
                        for i in range(10) for j in range(10)],
                  x="col", series=[{"key": "value", "label": "images"}], domain=[0, int(cm.max())],
                  note="Rows are true classes, columns predicted."),
            Chart(id="per-class", kind="hbar", title="Per-class accuracy",
                  data=[{"x": classes[i], "acc": round(float(per_class[i]), 4)} for i in range(10)],
                  series=[{"key": "acc", "label": "accuracy"}], valueFormat="percent"),
        ],
        tables=[Table("history", "Training history",
                      ["Epoch", "Train loss", "Val loss", "Train acc", "Val acc", "LR"],
                      [[h["epoch"], h["train_loss"], h["val_loss"], h["train_acc"], h["val_acc"], h["lr"]]
                       for h in history])],
        code_excerpt=(
            "for epoch in range(1, EPOCHS + 1):\n"
            "    model.train()                                   # dropout on, batchnorm learning\n"
            "    for xb, yb in train_dl:\n"
            "        xb, yb = xb.to(device), yb.to(device)\n"
            "        opt.zero_grad(set_to_none=True)\n"
            "        with torch.amp.autocast(device.type, enabled=use_amp):\n"
            "            loss = lossf(model(xb), yb)\n"
            "        scaler.scale(loss).backward()\n"
            "        scaler.unscale_(opt); nn.utils.clip_grad_norm_(model.parameters(), 1.0)\n"
            "        scaler.step(opt); scaler.update()\n\n"
            "    model.eval()                                    # dropout off, batchnorm frozen\n"
            "    with torch.no_grad():                           # no graph built\n"
            "        val_acc = evaluate(model, test_dl)\n"
            "    sched.step()\n"
            "    if val_acc > best_acc:                          # checkpoint on improvement only\n"
            "        torch.save({'model_state': model.state_dict(),\n"
            "                    'optimizer_state': opt.state_dict(), 'epoch': epoch}, ckpt)"
        ),
        takeaway=f"{best_acc:.1%} accuracy in {train_seconds:.0f}s of CPU -- and forgetting `model.eval()` "
                 f"would silently cost {best_acc - train_mode_acc:.1%} of it.",
        artifacts=["artifacts/fashion_cnn.pt"],
    )


if __name__ == "__main__":
    print("\n=== CRISP-DM 4 (heavy): pytorch-training-loop ===")
    emit(run())
