"""Transparent in-play benchmark example; no external API and no trade submission."""
from wcdrawlab.inplay import InPlayState, update_inplay_probabilities

state = InPlayState(minute=67, goals_a=0, goals_b=1, red_cards_a=0, red_cards_b=0, xg_a=0.92, xg_b=0.71)
pred = update_inplay_probabilities(1.45, 0.95, state)
print(pred)
