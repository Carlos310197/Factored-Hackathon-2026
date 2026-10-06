from evalkit.goals import GoalCard


def make_card(**overrides) -> GoalCard:
    base = dict(goal_id="H001-dispute_auto", split="heldout", group="dispute_auto", language="es",
                customer_id="CLI-T1", country="México", segment="Retail",
                persona={"verbosity": "normal", "vagueness": "low", "patience": "normal"},
                hidden_goal="You want to dispute your purchase of 100.00 USD on 2026-06-14 at Oxxo.",
                revealable_facts={"date": "2026-06-14", "amount": 100.0, "currency": "USD", "merchant": "Oxxo"},
                expected={"outcome": "resolve", "action": "dispute:TRX-A1:duplicate_charge", "handoff_reasons": [],
                          "must_not": []},
                allowed_ids=["TRX-A1", "TRX-A2", "PRD-P1"])
    return GoalCard(**(base | overrides))
