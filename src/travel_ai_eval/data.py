"""Load the inventory and golden dataset from disk."""

from pathlib import Path

from pydantic import TypeAdapter

from travel_ai_eval.config import DATA_DIR
from travel_ai_eval.models.schemas import GoldenDataset, InventoryItem

INVENTORY_PATH = DATA_DIR / "travel_inventory.json"
DATASET_PATH = DATA_DIR / "golden_dataset.json"

_inventory_adapter = TypeAdapter(list[InventoryItem])


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Required data file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_inventory(path: Path = INVENTORY_PATH) -> list[InventoryItem]:
    items = _inventory_adapter.validate_json(_read(path))
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate hotel ids in inventory")
    return items


def load_dataset(path: Path = DATASET_PATH) -> GoldenDataset:
    dataset = GoldenDataset.model_validate_json(_read(path))
    ids = [c.id for c in dataset.cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ids in golden dataset")
    return dataset
