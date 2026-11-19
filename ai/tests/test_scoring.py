from datetime import date, datetime, timedelta, timezone

import pytest

from app.scoring import FEATURES, features, real_samples, score_open_deals, train

NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


def deal(id_=1, stage="offer", value=1_000_000, age=20, idle=2, notes=2, close_in=10, price=1_000_000,
         budget=(900_000, 1_100_000), closed_ago=None, last_open_stage=None):
    return {
        "id": id_, "stage": stage, "value": value,
        "created_at": (NOW - timedelta(days=age)).replace(tzinfo=None),
        "last_activity_at": (NOW - timedelta(days=idle)).replace(tzinfo=None),
        "note_count": notes,
        "expected_close_date": (NOW + timedelta(days=close_in)).date() if close_in is not None else None,
        "closed_at": (NOW - timedelta(days=closed_ago)).replace(tzinfo=None) if closed_ago is not None else None,
        "property_price": price, "budget_min": budget[0], "budget_max": budget[1],
        "last_open_stage": last_open_stage,
    }


def test_features():
    x = dict(zip(FEATURES, features(deal(stage="negotiation", close_in=-15, value=950_000), "negotiation", NOW)))

    assert x["stage_progress"] == 1.0
    assert x["overdue_months"] == pytest.approx(0.5)
    assert x["price_gap"] == pytest.approx(0.05)
    assert x["budget_fit"] == 1.0 and x["has_property"] == 1.0


@pytest.fixture(scope="module")
def model():
    return train([], synthetic=3000, epochs=250)


def test_model_learns_the_expected_directions(model):
    w = dict(zip(FEATURES, model.weight.tolist()))

    assert w["stage_progress"] > 0
    assert w["log_days_since_activity"] < 0
    assert w["overdue_months"] < 0
    assert w["budget_fit"] > 0
    assert w["price_gap"] < 0


def test_later_stage_and_recent_activity_score_higher(model):
    [lead, negotiation] = model.predict([features(deal(stage="lead"), "lead", NOW), features(deal(stage="negotiation"), "negotiation", NOW)])
    [fresh, stale] = model.predict([features(deal(idle=1), "offer", NOW), features(deal(idle=60), "offer", NOW)])

    assert negotiation > lead + 0.2
    assert fresh > stale


def test_training_is_deterministic():
    a, b = train([], synthetic=500, epochs=50), train([], synthetic=500, epochs=50)
    assert a.weight.tolist() == b.weight.tolist()


def test_real_samples_use_the_stage_before_closing_and_skip_unknown():
    rows = [
        deal(1, stage="won", closed_ago=3, last_open_stage="negotiation"),
        deal(2, stage="lost", closed_ago=3, last_open_stage="lead"),
        deal(3, stage="won", closed_ago=3, last_open_stage=None),  # closed without a logged stage change
        deal(4, stage="offer"),  # still open
    ]
    xs, ys = real_samples(rows)

    assert ys == [1.0, 0.0]
    assert [x[0] for x in xs] == [1.0, 0.0]  # stage_progress taken from last_open_stage, not "won"


def test_real_outcomes_are_counted_and_shift_the_model():
    lost_late = [deal(i, stage="lost", closed_ago=2, last_open_stage="negotiation") for i in range(30)]
    base, shifted = train([], synthetic=1000, epochs=150), train(lost_late, synthetic=1000, epochs=150)
    x = features(deal(stage="negotiation"), "negotiation", NOW)

    assert shifted.trained_on == {"simulated": 1000, "real_closed_deals": 30}
    assert shifted.predict([x])[0] < base.predict([x])[0]


def test_scores_only_open_deals_with_readable_drivers(model):
    rows = [deal(1, stage="negotiation", idle=30, close_in=-20), deal(2, stage="won", closed_ago=1)]

    [scored] = score_open_deals(model, rows, NOW)

    assert scored["deal_id"] == 1 and 0 < scored["probability"] < 1
    labels = [d["label"] for d in scored["drivers"]]
    assert "Negotiation stage" in labels
    assert any(l.startswith("No activity for 30 days") or l.startswith("Expected close passed 20 days") for l in labels)
    assert {d["effect"] for d in scored["drivers"]} <= {"up", "down"}
