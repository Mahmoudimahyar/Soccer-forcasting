from wcdrawlab.inplay import InPlayState, update_inplay_probabilities


def test_inplay_probabilities_sum_to_one_and_lead_matters():
    early = update_inplay_probabilities(1.5, 1.1, InPlayState(minute=10, goals_a=0, goals_b=0))
    late_lead = update_inplay_probabilities(1.5, 1.1, InPlayState(minute=80, goals_a=1, goals_b=0))
    assert abs(early.p_a_win + early.p_draw + early.p_b_win - 1) < 1e-9
    assert late_lead.p_a_win > early.p_a_win
    assert late_lead.p_draw_ci_low <= late_lead.p_draw <= late_lead.p_draw_ci_high
