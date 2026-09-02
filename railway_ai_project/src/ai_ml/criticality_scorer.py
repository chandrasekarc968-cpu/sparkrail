"""
Criticality Scorer Module.
Uses XGBoost to predict asset degradation and calculate a Task Criticality Index.
"""
from typing import Any
import xgboost as xgb
import numpy as np

class TaskCriticalityModel:
    """Predictive model for railway asset degradation and task criticality."""
    
    def __init__(self) -> None:
        """Initialize the XGBoost Regressor."""
        self.model: xgb.XGBRegressor = xgb.XGBRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5
        )

    def train(self, x_train: np.ndarray, y_train: np.ndarray) -> None:
        """
        Trains the XGBoost model.
        
        Args:
            x_train (np.ndarray): Feature matrix representing asset conditions.
            y_train (np.ndarray): Target vector representing degradation or criticality.
        """
        self.model.fit(x_train, y_train)

    def predict(self, x_features: np.ndarray) -> np.ndarray:
        """
        Calculates the Task Criticality Index for pending jobs.
        
        Args:
            x_features (np.ndarray): Feature matrix of pending jobs.
            
        Returns:
            np.ndarray: Predicted criticality indices.
        """
        return self.model.predict(x_features)
