"""DistilBERT fine-tuned on CPU for the sentiment comparison (SPEC §8.3: at most 3 epochs).

A plain PyTorch loop (no Trainer/accelerate), short inputs (128 tokens) and a fixed seed, so it
finishes in minutes on a 4-core CPU. Used only by `ml.evaluate --finetune`.
"""

import random

from app.nlp import registry

LABELS = ["negative", "neutral", "positive"]
EPOCHS = 2
MAX_LEN = 128
BATCH = 16
LR = 5e-5
SEED = 2026


def finetune_predict(train: list[tuple[str, str]], test_texts: list[str]) -> list[str]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    repo = registry.eval_model_id("finetune_base")
    torch.manual_seed(SEED)
    rng = random.Random(SEED)
    tokenizer = AutoTokenizer.from_pretrained(repo)
    model = AutoModelForSequenceClassification.from_pretrained(repo, num_labels=len(LABELS))
    optimiser = torch.optim.AdamW(model.parameters(), lr=LR)
    rows = [(text, LABELS.index(label)) for text, label in train]
    steps = EPOCHS * ((len(rows) + BATCH - 1) // BATCH)
    schedule = torch.optim.lr_scheduler.LinearLR(optimiser, 1.0, 0.0, total_iters=steps)

    model.train()
    for _ in range(EPOCHS):
        rng.shuffle(rows)
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            enc = tokenizer(
                [t for t, _ in batch],
                padding=True,
                truncation=True,
                max_length=MAX_LEN,
                return_tensors="pt",
            )
            loss = model(**enc, labels=torch.tensor([y for _, y in batch])).loss
            loss.backward()
            optimiser.step()
            schedule.step()
            optimiser.zero_grad()

    model.eval()
    out: list[str] = []
    with torch.inference_mode():
        for i in range(0, len(test_texts), 32):
            enc = tokenizer(
                test_texts[i : i + 32],
                padding=True,
                truncation=True,
                max_length=MAX_LEN,
                return_tensors="pt",
            )
            out += [LABELS[j] for j in model(**enc).logits.argmax(-1).tolist()]
    return out
