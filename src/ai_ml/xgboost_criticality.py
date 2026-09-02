"""
XGBoost-based predictive model to calculate the Task Criticality Index.
"""
import xgboost as xgb

class TaskCriticalityModel:
    def __init__(self):
        self.model = xgb.XGBRegressor()

    def train(self, X_train, y_train):
        """Train the model to predict criticality index."""
        self.model.fit(X_train, y_train)

    def predict(self, X):
        """Calculate the Task Criticality Index for given tasks."""
        return self.model.predict(X)
