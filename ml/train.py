"""
Sanjeevani AI - severity model training.

Reads  ml/out/ddi_dataset.csv   (built by kb_source.py, optionally enriched by kaggle_ingest.py)
Writes backend/app/ml_artifacts/{model.json, meta.json, metrics.json}
       docs/figures/*.png

Two evaluations are reported on purpose:
  1. Random stratified split   -> optimistic (the data is rule-generated, so it is nearly memorisable)
  2. Leave-class-pair-out CV   -> honest: every test pair belongs to a drug-class pair never seen in training
"""
import csv, json, os, sys, datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support, confusion_matrix,
                             roc_curve, auc, roc_auc_score, classification_report)
from sklearn.model_selection import train_test_split, StratifiedKFold, GroupKFold, cross_val_score
from sklearn.preprocessing import label_binarize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "out", "ddi_dataset.csv")
ART = os.path.join(ROOT, "backend", "app", "ml_artifacts")
FIG = os.path.join(ROOT, "docs", "figures")
os.makedirs(ART, exist_ok=True); os.makedirs(FIG, exist_ok=True)

LABELS = ["None", "Minor", "Moderate", "Major"]   # fixed order = class index used by the backend
SEED = 42

rows = list(csv.DictReader(open(DATA, encoding="utf-8")))
tags = sorted({t for r in rows for t in (r["tags_a"].split(";") + r["tags_b"].split(";")) if t})
classes = sorted({r["class_a"] for r in rows} | {r["class_b"] for r in rows})
tag_i = {t: i for i, t in enumerate(tags)}
cls_i = {c: i for i, c in enumerate(classes)}


def featurize(tags_a, tags_b, class_a, class_b):
    a = np.zeros(len(tags)); b = np.zeros(len(tags))
    for t in tags_a:
        if t in tag_i: a[tag_i[t]] = 1
    for t in tags_b:
        if t in tag_i: b[tag_i[t]] = 1
    ci = sorted([cls_i.get(class_a, 0), cls_i.get(class_b, 0)])
    return np.concatenate([np.maximum(a, b), np.minimum(a, b), ci])


X = np.array([featurize(r["tags_a"].split(";"), r["tags_b"].split(";"), r["class_a"], r["class_b"]) for r in rows])
y = np.array([LABELS.index(r["severity"]) for r in rows])
groups = np.array([" | ".join(sorted([r["class_a"], r["class_b"]])) for r in rows])
feat_names = [f"either_{t}" for t in tags] + [f"both_{t}" for t in tags] + ["class_idx_1", "class_idx_2"]
print(f"samples={len(rows)} features={X.shape[1]} tags={len(tags)} classes={len(classes)} class_pairs={len(set(groups))}")

models = {
    "RandomForest": lambda: RandomForestClassifier(n_estimators=300, max_depth=14, class_weight="balanced", random_state=SEED, n_jobs=-1),
    "XGBoost": lambda: xgb.XGBClassifier(n_estimators=250, max_depth=6, learning_rate=0.1, subsample=0.9, colsample_bytree=0.9,
                                         objective="multi:softprob", eval_metric="mlogloss", random_state=SEED, n_jobs=2),
    "LogisticRegression": lambda: LogisticRegression(max_iter=3000, class_weight="balanced"),
}

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
results = {}
for name, make in models.items():
    m = make().fit(Xtr, ytr)
    p = m.predict(Xte)
    pr, rc, f1, _ = precision_recall_fscore_support(yte, p, average="weighted", zero_division=0)
    cv = cross_val_score(make(), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED), scoring="accuracy")
    # leave-class-pair-out
    gacc, gf1 = [], []
    for tr, te in GroupKFold(5).split(X, y, groups):
        present = np.unique(y[tr]); remap = {c: i for i, c in enumerate(present)}
        gm = make().fit(X[tr], np.array([remap[c] for c in y[tr]]))
        gp = present[gm.predict(X[te])]
        gacc.append(accuracy_score(y[te], gp))
        gf1.append(precision_recall_fscore_support(y[te], gp, average="weighted", zero_division=0)[2])
    results[name] = dict(model=m, pred=p, accuracy=accuracy_score(yte, p), precision=pr, recall=rc, f1=f1,
                         cv_accuracy=float(cv.mean()), cv_std=float(cv.std()),
                         group_cv_accuracy=float(np.mean(gacc)), group_cv_f1=float(np.mean(gf1)))
    print(f"{name:20s} acc={results[name]['accuracy']:.3f} f1={f1:.3f} cv={cv.mean():.3f} | leave-class-pair-out acc={np.mean(gacc):.3f} f1={np.mean(gf1):.3f}")

best = "XGBoost"  # served model: native JSON export is version-robust and has probability outputs
bm = results[best]["model"]
proba = bm.predict_proba(Xte)
yb = label_binarize(yte, classes=list(range(len(LABELS))))
per_class_auc = {}
for i, l in enumerate(LABELS):
    if yb[:, i].sum() > 0:
        per_class_auc[l] = float(roc_auc_score(yb[:, i], proba[:, i]))
macro_auc = float(np.mean(list(per_class_auc.values())))
rep = classification_report(yte, results[best]["pred"], labels=list(range(len(LABELS))), target_names=LABELS, zero_division=0, output_dict=True)

# --- export for the backend (no sklearn needed at runtime) ---
bm.get_booster().save_model(os.path.join(ART, "model.json"))
json.dump({"labels": LABELS, "tags": tags, "classes": classes, "n_features": int(X.shape[1]),
           "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "n_samples": len(rows)},
          open(os.path.join(ART, "meta.json"), "w"), indent=1)
metrics = {
    "best_model": best, "n_samples": len(rows), "n_features": int(X.shape[1]), "n_tags": len(tags), "n_classes": len(classes),
    "label_counts": {l: int((y == i).sum()) for i, l in enumerate(LABELS)},
    "models": {n: {k: v for k, v in r.items() if k not in ("model", "pred")} for n, r in results.items()},
    "macro_roc_auc": macro_auc, "per_class_auc": per_class_auc,
    "per_class_report": {l: {k: float(rep[l][k]) for k in ("precision", "recall", "f1-score", "support")} for l in LABELS},
    "notes": ("Random-split scores are optimistic because labels are generated from authored class-pair rules. "
              "group_cv_* (leave-class-pair-out) estimates behaviour on class pairs with no authored rule and is the number to trust."),
}
json.dump(metrics, open(os.path.join(ART, "metrics.json"), "w"), indent=1)

# --- figures ---
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
cm = confusion_matrix(yte, results[best]["pred"], labels=list(range(len(LABELS))))
fig, ax = plt.subplots(figsize=(5.2, 4.4)); im = ax.imshow(cm, cmap="Greens")
ax.set_xticks(range(4)); ax.set_yticks(range(4)); ax.set_xticklabels(LABELS); ax.set_yticklabels(LABELS)
for i in range(4):
    for j in range(4):
        ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title(f"Confusion matrix - {best} (random 20% test)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "confusion_matrix.png"), dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(7.2, 4.4)); x = np.arange(len(results)); w = 0.26
ax.bar(x - w, [r["accuracy"] for r in results.values()], w, label="Random split accuracy", color="#0f766e")
ax.bar(x, [r["cv_accuracy"] for r in results.values()], w, label="5-fold CV accuracy", color="#5eead4")
ax.bar(x + w, [r["group_cv_accuracy"] for r in results.values()], w, label="Leave-class-pair-out accuracy", color="#f59e0b")
ax.set_xticks(x); ax.set_xticklabels(results.keys()); ax.set_ylim(0, 1.05); ax.set_ylabel("Accuracy"); ax.legend(loc="lower left", fontsize=8)
ax.set_title("Model comparison: optimistic vs. honest evaluation"); fig.tight_layout(); fig.savefig(os.path.join(FIG, "model_comparison.png"), dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(5.6, 4.6))
for i, l in enumerate(LABELS):
    if yb[:, i].sum() > 0:
        fpr, tpr, _ = roc_curve(yb[:, i], proba[:, i]); ax.plot(fpr, tpr, label=f"{l} (AUC {auc(fpr, tpr):.3f})")
ax.plot([0, 1], [0, 1], "k--", alpha=.3); ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate")
ax.set_title("One-vs-rest ROC (XGBoost)"); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(os.path.join(FIG, "roc_curves.png"), dpi=150); plt.close(fig)

imp = bm.feature_importances_; top = np.argsort(imp)[-15:]
fig, ax = plt.subplots(figsize=(6.6, 4.8)); ax.barh([feat_names[i] for i in top], imp[top], color="#0f766e")
ax.set_title("Top 15 features (XGBoost)"); fig.tight_layout(); fig.savefig(os.path.join(FIG, "feature_importance.png"), dpi=150); plt.close(fig)
print("saved artifacts ->", ART)
