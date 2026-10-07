"""The candidate models, built for a chosen set of feature groups."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from ..dataset.features import FEATURE_GROUPS
from .quantile_gbm import QuantileGBM
from .sigma_models import SigmaModel, ebm, gbm, ridge

ALL_GROUPS = tuple(FEATURE_GROUPS)
MODEL_NAMES = ("ridge_sigma", "gbm_sigma", "ebm_sigma", "gbm_quantile")


def features_for(groups: Iterable[str]) -> List[str]:
    unknown = set(groups) - set(FEATURE_GROUPS)
    if unknown:
        raise ValueError(f"unknown feature groups {sorted(unknown)}; known: {list(FEATURE_GROUPS)}")
    return [f for g in FEATURE_GROUPS if g in set(groups) for f in FEATURE_GROUPS[g]]


def build(name: str, groups: Optional[Sequence[str]] = None):
    feats = features_for(groups or ALL_GROUPS)
    if name == "ridge_sigma":
        return SigmaModel(name, ridge, feats)
    if name == "gbm_sigma":
        return SigmaModel(name, gbm, feats)
    if name == "ebm_sigma":
        return SigmaModel(name, ebm, feats)
    if name == "gbm_quantile":
        return QuantileGBM(feats, name=name)
    raise ValueError(f"unknown model {name!r}; known: {list(MODEL_NAMES)}")


def all_models(groups: Optional[Sequence[str]] = None):
    return [build(n, groups) for n in MODEL_NAMES]
