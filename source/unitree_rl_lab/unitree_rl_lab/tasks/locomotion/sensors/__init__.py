"""Sensors shared across locomotion tasks (视觉/激光雷达等外��感知传感器).

Kept outside ``robots/`` on purpose: a sensor model is a property of the *hardware*, not of
one robot task, so GO2 and the GeesunDog variants can reuse the same spec without
cross-contaminating each other's reward / curriculum knobs (see the note at the top of
``robots/geesun_dog/lingsi_d30w/velocity_env_cfg.py`` about the two campaigns being tuned
independently).
"""