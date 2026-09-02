"""
PyTorch Geometric module for representing the heterogeneous graph structure of the railway network.
"""
import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv

class RailwayGNN(torch.nn.Module):
    def __init__(self, num_node_features, hidden_channels):
        super(RailwayGNN, self).__init__()
        self.conv1 = GCNConv(num_node_features, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        self.out = torch.nn.Linear(hidden_channels, 1)

    def forward(self, x, edge_index):
        # First Graph Convolutional Layer
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.5, training=self.training)
        
        # Second Graph Convolutional Layer
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        
        # Output Layer
        out = self.out(x)
        return out
