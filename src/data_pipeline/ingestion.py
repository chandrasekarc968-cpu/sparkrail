import json
import os
import logging
from typing import Dict, Any, Optional
from pydantic import ValidationError
from src.data_pipeline.models import Scenario

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("DataIngestor")

class DataIngestionError(Exception):
    pass

class DataIngestor:
    """
    Handles data ingestion from either local synthetic fixtures or Kafka/PostGIS.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_local = config.get("data_pipeline", {}).get("use_local_synthetic", True)
        self.local_path = config.get("data_pipeline", {}).get("synthetic_data_path", "data/synthetic")
        
    def load_scenario(self) -> Scenario:
        """Loads the current railway scenario data."""
        logger.info(f"Loading scenario data. Local mode: {self.use_local}")
        try:
            if self.use_local:
                return self._load_local_scenario()
            else:
                return self._load_remote_scenario()
        except ValidationError as e:
            logger.error(f"Schema validation failed during ingestion: {e}")
            raise DataIngestionError("Invalid data format") from e
        except Exception as e:
            logger.error(f"Unexpected error during ingestion: {e}")
            raise DataIngestionError(str(e)) from e

    def _load_local_scenario(self) -> Scenario:
        """Loads data from a local JSON fixture."""
        file_path = os.path.join(self.local_path, "scenario.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Synthetic data file not found at {file_path}. Run generate-data first.")
            
        with open(file_path, "r") as f:
            data = json.load(f)
            
        scenario = Scenario(**data)
        logger.info(f"Loaded local scenario with {len(scenario.blocks)} blocks, {len(scenario.jobs)} jobs, {len(scenario.trains)} trains.")
        return scenario
        
    def _load_remote_scenario(self) -> Scenario:
        """Placeholder for Kafka/PostGIS integration."""
        logger.warning("Remote Kafka/PostGIS ingestion not fully implemented. Connection parameters check bypassed.")
        # We explicitly raise an error if remote is requested but not connected (as required by prompt).
        raise NotImplementedError("Remote Kafka/PostGIS ingestion is not implemented in local mode. Please use local synthetic data.")

    def map_chainage_to_block(self, chainage: float, scenario: Scenario) -> Optional[str]:
        """
        Maps a linear chainage coordinate to a discrete COA block section.
        """
        for block in scenario.blocks:
            if block.chainage_start <= chainage < block.chainage_end:
                return block.id
        return None
