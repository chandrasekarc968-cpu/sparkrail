"""
Proximal Policy Optimisation (PPO) tactical dispatch agent (Spec §3.2).

Spec §3.2 calls for an online RL agent over the GNN state with a discrete action
space (hold train / shift block window / reroute) and a reward aligned to the
MILP objective. This module delivers a genuine PPO implementation:

* :class:`RailRLGym`       - wraps :class:`SUMODigitalTwin` (or any
  ``reset/step/close`` env) exposing the standard RL interface.
* :class:`PolicyNet`       - small actor-critic MLP (numpy, no torch required).
* :func:`train_ppo`        - collects trajectories, computes GAE advantages,
  and runs the **clipped surrogate** PPO update with a value-function loss.

The clipped objective and GAE are implemented with explicit NumPy gradients, so
the whole DRL loop runs and is testable without a GPU or PyTorch. A torch-backed
``PolicyNet`` can be supplied later without changing the training loop.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("SparkRail.PPO")

GAMMA = 0.99
LAMBDA = 0.95
CLIP_EPS = 0.2
VALUE_COEF = 0.5
ENTROPY_COEF = 0.01


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


class PolicyNet:
    """Actor-critic MLP. Parameters are plain NumPy arrays (no autograd)."""

    def __init__(self, obs_dim: int, act_dim: int, hidden: int = 16, seed: int = 0):
        self.obs_dim = obs_dim
        self.act_dim = act_dim
        self.hidden = hidden
        rng = np.random.default_rng(seed)
        self.W1 = rng.standard_normal((hidden, obs_dim)) * 0.3
        self.b1 = np.zeros(hidden)
        self.W2 = rng.standard_normal((act_dim, hidden)) * 0.3
        self.b2 = np.zeros(act_dim)
        self.Wv = rng.standard_normal((1, hidden)) * 0.3
        self.bv = np.zeros(1)

    # ------------------------------------------------------------------ #
    def forward(self, obs: np.ndarray) -> Dict[str, np.ndarray]:
        h = np.maximum(0.0, self.W1 @ obs + self.b1)          # (hidden,)
        logits = self.W2 @ h + self.b2                        # (act,)
        value = float((self.Wv @ h + self.bv).item())          # scalar
        probs = _softmax(logits)
        return {"h": h, "logits": logits, "probs": probs, "value": value}

    @staticmethod
    def logp(probs: np.ndarray, action: int) -> float:
        return float(np.log(probs[action] + 1e-12))

    # ------------------------------------------------------------------ #
    def _grads(self, obs: np.ndarray, action: int, adv: float, ret: float,
               old_logp: float, clip: float) -> Dict[str, np.ndarray]:
        """Explicit gradients of (clipped policy loss + value loss) w.r.t. params."""
        f = self.forward(obs)
        h, logits, probs, value = f["h"], f["logits"], f["probs"], f["value"]
        new_logp = self.logp(probs, action)
        ratio = np.exp(new_logp - old_logp)
        unclipped = ratio * adv
        clipped = np.clip(ratio, 1 - clip, 1 + clip) * adv
        use_unclipped = unclipped <= clipped  # min() selected the unclipped term

        # Policy gradient contribution (only when not clipped)
        d_logits = np.zeros(self.act_dim)
        if use_unclipped and adv != 0.0:
            d_logits[action] = -adv * ratio  # d/dlogits of logp(a) is e_a - pi
            d_logits -= (-adv * ratio) * probs  # subtract prob term for all a
        # (Equivalently: d_logits = -adv*ratio*(e_a - probs); written explicitly above)
        d_logits = (-adv * ratio) * (np.eye(self.act_dim)[action] - probs) if use_unclipped else np.zeros(self.act_dim)

        dW2 = np.outer(d_logits, h)
        db2 = d_logits
        dh = self.W2.T @ d_logits
        dh[h <= 0] = 0.0  # ReLU derivative
        dW1 = np.outer(dh, obs)
        db1 = dh

        # Value gradient (MSE)
        dval = VALUE_COEF * (value - ret)
        dWv = dval * h.reshape(1, -1)
        dbv = np.array([dval])

        return {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2, "Wv": dWv, "bv": dbv}

    def apply_grads(self, grads: Dict[str, np.ndarray], lr: float) -> None:
        for k in grads:
            setattr(self, k, getattr(self, k) - lr * grads[k])


class RailRLGym:
    """RL wrapper around the digital-twin simulator."""

    def __init__(self, sim: Any, max_steps: int = 48):
        self.sim = sim
        self.max_steps = max_steps
        self.action_space = sim.action_space

    def reset(self) -> np.ndarray:
        return np.asarray(self.sim.reset(), dtype=float)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        ns, r, done, info = self.sim.step(action)
        return np.asarray(ns, dtype=float), float(r), bool(done), info

    @property
    def obs_dim(self) -> int:
        return len(self.reset())


def _collect(net: PolicyNet, gym: RailRLGym, max_steps: int) -> Dict[str, Any]:
    obs = gym.reset()
    states, actions, rewards, logps, values, dones = [], [], [], [], [], []
    for _ in range(max_steps):
        f = net.forward(obs)
        a = int(np.random.choice(net.act_dim, p=f["probs"]))
        ns, r, done, _ = gym.step(a)
        states.append(obs); actions.append(a); rewards.append(r)
        logps.append(PolicyNet.logp(f["probs"], a)); values.append(f["value"]); dones.append(done)
        obs = ns
        if done:
            break
    return {"states": states, "actions": actions, "rewards": rewards,
            "logps": logps, "values": values, "dones": dones,
            "ep_return": float(sum(rewards))}


def _gae(rewards: List[float], values: List[float], dones: List[bool],
         gamma: float = GAMMA, lam: float = LAMBDA) -> Tuple[List[float], List[float]]:
    adv = [0.0] * len(rewards)
    gae = 0.0
    next_v = 0.0
    for t in reversed(range(len(rewards))):
        non_term = 0.0 if dones[t] else 1.0
        delta = rewards[t] + gamma * next_v * non_term - values[t]
        gae = delta + gamma * lam * non_term * gae
        adv[t] = gae
        next_v = values[t]
    returns = [a + v for a, v in zip(adv, values)]
    # normalise advantages for stable updates
    if len(adv) > 1:
        adv = [(x - np.mean(adv)) / (np.std(adv) + 1e-8) for x in adv]
    return adv, returns


def train_ppo(gym: RailRLGym, net: Optional[PolicyNet] = None,
              episodes: int = 40, max_steps: int = 48, epochs: int = 4,
              lr: float = 0.01, batch: int = 32, seed: int = 0,
              clip: float = CLIP_EPS) -> Tuple[PolicyNet, List[float]]:
    """
    Train the PPO policy. Returns the trained net and per-episode returns
    (used as a convergence signal in tests/benchmarks).
    """
    if net is None:
        net = PolicyNet(gym.obs_dim, len(gym.action_space), seed=seed)
    history: List[float] = []

    for ep in range(episodes):
        traj = _collect(net, gym, max_steps)
        history.append(traj["ep_return"])
        if len(traj["states"]) < 2:
            continue
        adv, rets = _gae(traj["rewards"], traj["values"], traj["dones"])
        # PPO minibatch update
        idx = np.arange(len(traj["states"]))
        for _ in range(epochs):
            rng = np.random.default_rng(ep)
            rng.shuffle(idx)
            for start in range(0, len(idx), batch):
                mb = idx[start:start + batch]
                acc = {k: np.zeros_like(getattr(net, k)) for k in
                       ("W1", "b1", "W2", "b2", "Wv", "bv")}
                for i in mb:
                    g = net._grads(
                        np.asarray(traj["states"][i], dtype=float),
                        int(traj["actions"][i]),
                        float(adv[i]), float(rets[i]), float(traj["logps"][i]), clip,
                    )
                    for k in acc:
                        acc[k] += g[k]
                for k in acc:
                    acc[k] /= max(1, len(mb))
                net.apply_grads(acc, lr)

    logger.info("PPO training complete: %d episodes, final return %.3f",
                episodes, history[-1] if history else 0.0)
    return net, history
