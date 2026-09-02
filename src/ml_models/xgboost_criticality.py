"""
XGBoost model for evaluating task criticality index.
"""
import xgboost as xgb

class TaskCriticalityPredictor:
    def __init__(self, config=None):
        self.model = xgb.XGBRegressor()
        self.config = config

    def train(self, X_train, y_train):
        """Train the XGBoost model."""
        self.model.fit(X_train, y_train)

    def predict(self, X_test):
        """Predict task criticality."""
        return self.model.predict(X_test)

    def save_model(self, path=None):
        save_path = path or self.config['ml']['xgboost_model_path']
        self.model.save_model(save_path)

    def load_model(self, path=None):
        load_path = path or self.config['ml']['xgboost_model_path']
        self.model.load_model(load_path)
