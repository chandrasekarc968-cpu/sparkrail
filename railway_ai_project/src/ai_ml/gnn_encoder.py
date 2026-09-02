"""
GNN State Encoder Module.
Uses PyTorch Geometric to create a Heterogeneous GNN for network representation.
Transforms raw physical states into rich spatial embeddings.
"""
from typing import Dict, Tuple
import torch
import torch.nn.functional as F
from torch_geometric.nn import HeteroConv, SAGEConv, Linear
from torch import Tensor

class RailwayStateEncoder(torch.nn.Module):
    """
    Heterogeneous Graph Neural Network to encode dynamic railway states.
    Nodes: 'train', 'track', 'station'
    Edges: ('train', 'occupies', 'track'), ('track', 'connects', 'track'), ('station', 'on', 'track')
    """
    
    def __init__(self, in_channels_dict: Dict[str, int], hidden_channels: int, out_channels: int) -> None:
        """
        Initialize the GNN encoder.
        
        Args:
            in_channels_dict (Dict[str, int]): Dictionary of input feature dimensions per node type.
            hidden_channels (int): Dimensionality of hidden layers.
            out_channels (int): Dimensionality of output embeddings.
        """
        super().__init__()
        
        # 1. Input Transformation: map diverse raw features into uniform hidden dimensions
        self.lin_dict = torch.nn.ModuleDict()
        for node_type, in_channels in in_channels_dict.items():
            self.lin_dict[node_type] = Linear(in_channels, hidden_channels)
            
        # 2. First Message Passing Layer (Heterogeneous SAGEConv)
        self.conv1 = HeteroConv({
            ('train', 'occupies', 'track'): SAGEConv(hidden_channels, hidden_channels),
            ('track', 'occupied_by', 'train'): SAGEConv(hidden_channels, hidden_channels),
            ('track', 'connects', 'track'): SAGEConv(hidden_channels, hidden_channels),
            ('station', 'on', 'track'): SAGEConv(hidden_channels, hidden_channels),
            ('track', 'has', 'station'): SAGEConv(hidden_channels, hidden_channels),
        }, aggr='mean')
        
        # 3. Second Message Passing Layer
        self.conv2 = HeteroConv({
            ('train', 'occupies', 'track'): SAGEConv(hidden_channels, out_channels),
            ('track', 'occupied_by', 'train'): SAGEConv(hidden_channels, out_channels),
            ('track', 'connects', 'track'): SAGEConv(hidden_channels, out_channels),
            ('station', 'on', 'track'): SAGEConv(hidden_channels, out_channels),
            ('track', 'has', 'station'): SAGEConv(hidden_channels, out_channels),
        }, aggr='mean')

    def forward(self, x_dict: Dict[str, Tensor], edge_index_dict: Dict[Tuple[str, str, str], Tensor]) -> Dict[str, Tensor]:
        """
        Forward pass for the GNN encoder.
        
        Args:
            x_dict (Dict[str, Tensor]): Dictionary mapping node type to its feature tensor.
            edge_index_dict (Dict[Tuple, Tensor]): Dictionary mapping edge relation to its index tensor (2xN).
            
        Returns:
            Dict[str, Tensor]: Output embeddings mapping node type to a refined tensor.
        """
        # Transform inputs
        out_dict = {}
        for node_type, x in x_dict.items():
            out_dict[node_type] = F.leaky_relu(self.lin_dict[node_type](x))
            
        # Pass 1
        out_dict = self.conv1(out_dict, edge_index_dict)
        out_dict = {key: F.leaky_relu(x) for key, x in out_dict.items()}
        
        # Pass 2
        out_dict = self.conv2(out_dict, edge_index_dict)
        
        return out_dict
