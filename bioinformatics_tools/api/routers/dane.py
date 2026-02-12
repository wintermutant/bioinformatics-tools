"""
MongoDB dane_entries CRUD endpoints.
"""
import os
from datetime import datetime

from fastapi import APIRouter
from pymongo import MongoClient

from bioinformatics_tools.api.models import DaneEntry

router = APIRouter(prefix="/v1/dane", tags=["dane"])

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password123@localhost:27017/")
client = MongoClient(MONGO_URI)
db = client['biotools']
collection = db['dane_entries']


@router.get("/entries")
async def get_dane_entries():
    """Get all dane entries as JSON"""
    entries = list(collection.find({}, {"_id": 0, "value": 1, "timestamp": 1}).sort("timestamp", -1))
    return {"entries": entries}


@router.post("/entries")
async def create_dane_entry(entry: DaneEntry):
    """Create a new dane entry"""
    new_entry = {
        "value": entry.value,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    collection.insert_one(new_entry)
    return {"success": True, "entry": {"value": new_entry["value"], "timestamp": new_entry["timestamp"]}}
