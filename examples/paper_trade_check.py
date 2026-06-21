"""Run the deterministic risk gate on a local sample intent. Does not send any order."""
from pathlib import Path
from wcdrawlab.trading.service import policy_from_yaml, intent_from_json, quote_from_json, state_from_json, evaluate_intent

root = Path(__file__).parents[1]
policy = policy_from_yaml(root / "configs/trading.yaml")
intent = intent_from_json(root / "data/live/example_trade_intent.json")
quote = quote_from_json(root / "data/live/example_market_quote.json")
state = state_from_json(root / "data/live/example_portfolio_state.json")
print(evaluate_intent(intent, quote, state, policy, confidence_score=0.72))
