"""Geesun dog locomotion tasks.

Each asset variant lives in its own sub-package with a *standalone* task definition so the
campaigns can be trained / auto-tuned independently:

- ``dog1``        -> ``Unitree-GeesunDog-Dog1-Velocity``        (footed quadruped)
- ``lingsi_d30w`` -> ``Unitree-GeesunDog-LingsiD30W-Velocity``  (D30W wheel-legged)

Shared pieces (URDF -> USD conversion, actuator models, articulation cfg) live in
``unitree_rl_lab.assets.robots.unitree``; everything task-level (terrain, rewards, curriculum,
actions) is per-variant. This package registers nothing itself - it only has to stay a package
so ``import_packages`` walks into the sub-packages.
"""
