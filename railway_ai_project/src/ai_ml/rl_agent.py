"""
Reinforcement Learning Policy Module.
Implements a PPO Actor-Critic model taking GNN state embeddings to output scheduling actions.
"""
from typing import Tuple
import torch
import torch.nn as nn
from torch import Tensor
from torch.distributions import Categorical

class PPORLAgent(nn.Module):
    """
    PPO Agent that uses concatenated GNN node embeddings for dispatching actions.
    Specifically designed for routing/holding decisions at conflict points.
    """
    
    def __init__(self, input_dim: int, num_actions: int) -> None:
        """
        Initialize the RL Agent policy and value networks.
        
        Args:
            input_dim (int): Dimensionality of the flattened input state (e.g., concatenated train/track embeddings).
            num_actions (int): Number of discrete scheduling actions.
        """
        super().__init__()
        
        # Shared multi-layer perceptron (MLP) feature extractor
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.ReLU()
        )
        
        # Actor Head: Outputs logits for categorical distribution
        self.actor_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, num_actions)
        )
        
        # Critic Head: Outputs baseline value V(s)
        self.critic_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

    def forward(self, state_embeddings: Tensor) -> Tuple[Categorical, Tensor]:
        """
        Forward pass to get the action distribution and state value.
        
        Args:
            state_embeddings (Tensor): Input feature tensor of shape [batch_size, input_dim].
            
        Returns:
            Tuple[Categorical, Tensor]: PyTorch Categorical distribution for actions and V(s).
        """
        features = self.feature_extractor(state_embeddings)
        
        # Action distribution
        action_logits = self.actor_head(features)
        action_dist = Categorical(logits=action_logits)
        
        # State value estimate
        state_value = self.critic_head(features)
        
        return action_dist, state_value

    def get_action(self, state_embeddings: Tensor) -> Tuple[Tensor, Tensor, Tensor]:
        """
        Sample an action for the given state, returning action, log_prob, and value.
        Used during trajectory collection.
        """
        dist, value = self.forward(state_embeddings)
        action = dist.sample()
        log_prob = dist.log_prob(action)
        return action, log_prob, value
        
    def evaluate_actions(self, state_embeddings: Tensor, actions: Tensor) -> Tuple[Tensor, Tensor, Tensor]:
        """
        Evaluate specific actions for PPO surrogate loss calculation.
        Used during policy update.
        """
        dist, value = self.forward(state_embeddings)
        log_probs = dist.log_prob(actions)
        entropy = dist.entropy()
        return log_probs, torch.squeeze(value), entropy
