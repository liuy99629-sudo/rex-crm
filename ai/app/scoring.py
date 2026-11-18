"""Deal win probability, trained with PyTorch.

Model: logistic regression on 8 standardised features (torch.nn.Linear + BCE loss). A linear model
is deliberate: each feature's contribution (weight × standardised value) is an honest explanation
an agent can read ("No activity for 21 days" pulls the chance down).

Training data:
1. A simulated prior: plausible pipeline snapshots with outcomes drawn from documented assumptions
   (later stages, recent activity and a price within budget win more often). This lets the model
   work on day one, before the agency has history.
2. The agency's real closed deals, weighted much higher. For each won/lost deal the features are
   rebuilt as they stood when it closed, using the stage it was in just before (logged by the CRM's
   stage-change history). Deals closed without a logged stage change are skipped rather than guessed.

As real outcomes accumulate they dominate the prior."""

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import torch

OPEN_STAGES = ["lead", "contacted", "inspection", "offer", "negotiation"]
FEATURES = [
    "stage_progress",       # 0 (lead) .. 1 (negotiation)
    "log_days_open",
    "log_days_since_activity",
    "log_notes",
    "overdue_months",       # months past the expected close date, capped at 3
    "budget_fit",           # 1 within budget, 0.4 stretch, 0 well over, 0.5 unknown
    "price_gap",            # |deal value / asking price - 1|, capped at 0.5
    "has_property",
]
REAL_SAMPLE_WEIGHT = 20.0
SYNTHETIC_SAMPLES = 4000
SEED = 7


# --- features -------------------------------------------------------------------------------

def _days(a: datetime | date | None, b: datetime | date) -> float:
    if a is None:
        return 0.0
    if isinstance(a, datetime) and isinstance(b, datetime):
        a = a if a.tzinfo else a.replace(tzinfo=timezone.utc)
        b = b if b.tzinfo else b.replace(tzinfo=timezone.utc)
        return max(0.0, (b - a).total_seconds() / 86400)
    a_d = a.date() if isinstance(a, datetime) else a
    b_d = b.date() if isinstance(b, datetime) else b
    return float((b_d - a_d).days)


def _budget_fit(value: int | None, low: int | None, high: int | None) -> float:
    if value is None or (low is None and high is None):
        return 0.5
    if high is not None and value > high * 1.1:
        return 0.0
    if high is not None and value > high:
        return 0.4
    return 1.0


def features(row: dict[str, Any], stage: str, as_of: datetime) -> list[float]:
    """Feature vector for one deal at time `as_of`, assuming it is in open `stage`."""
    days_open = _days(row["created_at"], as_of)
    last = row.get("last_activity_at") or row["created_at"]
    since_activity = _days(last, as_of)
    overdue = 0.0
    if row.get("expected_close_date"):
        overdue = max(0.0, -_days(as_of, row["expected_close_date"]))  # days past expected close
    price = row.get("property_price")
    gap = min(abs(row["value"] / price - 1), 0.5) if price else 0.0
    return [
        OPEN_STAGES.index(stage) / 4,
        math.log1p(days_open),
        math.log1p(since_activity),
        math.log1p(row.get("note_count") or 0),
        min(overdue / 30, 3.0),
        _budget_fit(row["value"], row.get("budget_min"), row.get("budget_max")),
        gap,
        1.0 if price else 0.0,
    ]


# --- simulated prior ------------------------------------------------------------------------

# Assumed effect sizes for the simulator (log-odds per unit of each feature, see FEATURES).
PRIOR_LOGIT = {
    "bias": -1.6,
    "stage_progress": 3.2,
    "log_days_open": -0.15,
    "log_days_since_activity": -0.45,
    "log_notes": 0.4,
    "overdue_months": -0.6,
    "budget_fit": 1.4,
    "price_gap": -4.0,
    "has_property": 0.3,
}


def simulate(n: int, generator: torch.Generator) -> tuple[torch.Tensor, torch.Tensor]:
    g = generator
    stage = torch.randint(0, 5, (n,), generator=g).float() / 4
    days_open = torch.empty(n).exponential_(1 / 40, generator=g) + 1
    since = torch.minimum(days_open, torch.empty(n).exponential_(1 / 10, generator=g))
    notes = torch.poisson(1 + 2 * stage, generator=g)
    overdue = torch.where(torch.rand(n, generator=g) < 0.25, torch.empty(n).exponential_(1 / 20, generator=g), torch.zeros(n))
    budget = torch.tensor([1.0, 0.4, 0.0, 0.5])[torch.multinomial(torch.tensor([0.65, 0.15, 0.05, 0.15]), n, True, generator=g)]
    has_prop = (torch.rand(n, generator=g) < 0.75).float()
    gap = (torch.randn(n, generator=g).abs() * 0.05).clamp(max=0.5) * has_prop

    x = torch.stack([stage, days_open.log1p(), since.log1p(), notes.log1p(), (overdue / 30).clamp(max=3), budget, gap, has_prop], 1)
    w = torch.tensor([PRIOR_LOGIT[f] for f in FEATURES])
    p = torch.sigmoid(x @ w + PRIOR_LOGIT["bias"])
    y = torch.bernoulli(p, generator=g)
    return x, y


# --- model ----------------------------------------------------------------------------------

@dataclass
class WinModel:
    weight: torch.Tensor
    bias: float
    mean: torch.Tensor
    std: torch.Tensor
    trained_on: dict[str, int] = field(default_factory=dict)
    trained_at: str = ""

    def logits(self, x: torch.Tensor) -> torch.Tensor:
        return ((x - self.mean) / self.std) @ self.weight + self.bias

    def predict(self, x: list[list[float]]) -> list[float]:
        with torch.no_grad():
            return torch.sigmoid(self.logits(torch.tensor(x, dtype=torch.float32))).tolist()

    def contributions(self, x: list[float]) -> dict[str, float]:
        z = (torch.tensor(x) - self.mean) / self.std * self.weight
        return dict(zip(FEATURES, z.tolist()))


def real_samples(rows: list[dict[str, Any]]) -> tuple[list[list[float]], list[float]]:
    xs, ys = [], []
    for r in rows:
        if r["stage"] in ("won", "lost") and r.get("last_open_stage") in OPEN_STAGES and r.get("closed_at"):
            xs.append(features(r, r["last_open_stage"], r["closed_at"]))
            ys.append(1.0 if r["stage"] == "won" else 0.0)
    return xs, ys


def train(rows: list[dict[str, Any]], synthetic: int = SYNTHETIC_SAMPLES, epochs: int = 300) -> WinModel:
    g = torch.Generator().manual_seed(SEED)
    torch.manual_seed(SEED)
    sx, sy = simulate(synthetic, g)
    rx, ry = real_samples(rows)
    x = torch.cat([sx, torch.tensor(rx, dtype=torch.float32).reshape(-1, len(FEATURES))])
    y = torch.cat([sy, torch.tensor(ry, dtype=torch.float32)])
    sample_w = torch.cat([torch.ones(len(sy)), torch.full((len(ry),), REAL_SAMPLE_WEIGHT)])

    mean, std = x.mean(0), x.std(0).clamp(min=1e-6)
    xn = (x - mean) / std
    linear = torch.nn.Linear(len(FEATURES), 1)
    opt = torch.optim.Adam(linear.parameters(), lr=0.05)
    loss_fn = torch.nn.BCEWithLogitsLoss(weight=sample_w)
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(linear(xn).squeeze(1), y)
        loss.backward()
        opt.step()

    return WinModel(
        weight=linear.weight.detach().squeeze(0),
        bias=float(linear.bias.detach()),
        mean=mean,
        std=std,
        trained_on={"simulated": len(sy), "real_closed_deals": len(ry)},
        trained_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# --- explanations ---------------------------------------------------------------------------

def _label(feature: str, raw: float, row: dict[str, Any], stage: str) -> str:
    if feature == "stage_progress":
        return f"{stage.capitalize()} stage"
    if feature == "log_days_since_activity":
        d = round(math.expm1(raw))
        if d <= 1:
            return "Activity in the last day"
        return f"Active in the last {d} days" if d <= 7 else f"No activity for {d} days"
    if feature == "log_notes":
        n = row.get("note_count") or 0
        return f"{n} note{'s' if n != 1 else ''} logged"
    if feature == "overdue_months":
        return f"Expected close passed {round(raw * 30)} days ago" if raw > 0 else "Not past the expected close date"
    if feature == "budget_fit":
        return {1.0: "Value within the client's budget", 0.4: "Value stretches the client's budget",
                0.0: "Value well over the client's budget"}.get(raw, "Client budget unknown")
    if feature == "price_gap":
        return f"Value {round(raw * 100)}% away from the asking price" if raw > 0.005 else "Value matches the asking price"
    if feature == "has_property":
        return "Linked to a listing" if raw else "No listing chosen yet"
    if feature == "log_days_open":
        return f"Open for {round(math.expm1(raw))} days"
    return feature


def score_open_deals(model: WinModel, rows: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    out = []
    for r in rows:
        if r["stage"] not in OPEN_STAGES:
            continue
        x = features(r, r["stage"], now)
        [p] = model.predict([x])
        contrib = model.contributions(x)
        ranked = sorted(contrib.items(), key=lambda kv: abs(kv[1]), reverse=True)
        drivers = [
            {"label": _label(f, x[FEATURES.index(f)], r, r["stage"]), "effect": "up" if c > 0 else "down"}
            for f, c in ranked[:3]
            if abs(c) >= 0.1
        ]
        out.append({"deal_id": r["id"], "probability": round(p, 3), "drivers": drivers})
    return out
