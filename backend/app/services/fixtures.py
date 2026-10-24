import json

from app.core.config import ROOT
from app.schemas.inputs import Dataset


def datasets() -> dict[str, Dataset]:
    result = {}
    for path in sorted((ROOT / "test_datasets").glob("*/*.json")):
        dataset = Dataset.model_validate(json.loads(path.read_text()))
        if dataset.id in result:
            raise ValueError(f"Duplicate dataset ID: {dataset.id}")
        result[dataset.id] = dataset
    return result
