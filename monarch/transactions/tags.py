"""Transaction tags: list, create, and non-destructively add/remove on a transaction.

Monarch's ``SetTransactionTags`` mutation is a FULL REPLACE — it overwrites a
transaction's entire tag list. So ``add``/``remove`` are implemented
read-union-write: read the transaction's current tags, compute the new set, and
write the full set. This is non-destructive (existing tags are preserved) and
idempotent in a quiescent system. Because the underlying API offers no
compare-and-set, callers must serialize tag writes — a concurrent external tag
change between the read and the write would be lost (last-writer-wins).
"""

from typing import Optional

from ..queries import (
    HOUSEHOLD_TAGS_QUERY,
    CREATE_TRANSACTION_TAG_MUTATION,
    SET_TRANSACTION_TAGS_MUTATION,
)
from ..client import APIError

# Monarch requires a color when creating a tag; this is a neutral default.
DEFAULT_TAG_COLOR = "#aaaaaa"


async def list_tags(client) -> list[dict]:
    """Return all household transaction tags (id, name, color, order)."""
    data = await client._request(HOUSEHOLD_TAGS_QUERY)
    return data.get("householdTransactionTags") or []


async def ensure_tag(client, name: str, color: Optional[str] = None) -> dict:
    """Find a tag by name (case-insensitive); create it if missing. Idempotent."""
    for tag in await list_tags(client):
        if (tag.get("name") or "").lower() == name.lower():
            return tag
    variables = {"input": {"name": name, "color": color or DEFAULT_TAG_COLOR}}
    data = await client._request(CREATE_TRANSACTION_TAG_MUTATION, variables)
    result = data.get("createTransactionTag", {})
    if result.get("errors"):
        raise APIError(f"Create tag failed: {result['errors']}")
    return result.get("tag", {})


async def set_transaction_tags(client, transaction_id: str, tag_ids: list[str]) -> dict:
    """RAW full-replace of a transaction's tags.

    Prefer ``add_transaction_tag`` / ``remove_transaction_tag`` — this overwrites
    the entire tag list and will drop any tag not present in ``tag_ids``.
    """
    variables = {"input": {"transactionId": transaction_id, "tagIds": tag_ids}}
    data = await client._request(SET_TRANSACTION_TAGS_MUTATION, variables)
    result = data.get("setTransactionTags", {})
    if result.get("errors"):
        raise APIError(f"Set tags failed: {result['errors']}")
    return result.get("transaction", {})


async def _current_tag_ids(client, transaction_id: str) -> list[str]:
    from .get import get_transaction
    txn = await get_transaction(client, transaction_id)
    if not txn:
        raise APIError(f"Transaction not found: {transaction_id}")
    return [t["id"] for t in (txn.get("tags") or [])]


async def add_transaction_tag(
    client, transaction_id: str, tag_name: str, color: Optional[str] = None
) -> dict:
    """Add a tag to a transaction WITHOUT losing its existing tags.

    Resolves (or creates) the tag by name, reads the transaction's current tags,
    and writes the union. Idempotent — adding an already-present tag is a no-op.
    """
    tag = await ensure_tag(client, tag_name, color)
    current = await _current_tag_ids(client, transaction_id)
    new_ids = list(dict.fromkeys(current + [tag["id"]]))  # order-stable union
    return await set_transaction_tags(client, transaction_id, new_ids)


async def remove_transaction_tag(client, transaction_id: str, tag_name: str) -> dict:
    """Remove a tag from a transaction, preserving the others. No-op if absent."""
    matching = [t for t in await list_tags(client)
                if (t.get("name") or "").lower() == tag_name.lower()]
    current = await _current_tag_ids(client, transaction_id)
    if not matching:
        from .get import get_transaction
        return await get_transaction(client, transaction_id) or {}
    remove_ids = {t["id"] for t in matching}
    new_ids = [tid for tid in current if tid not in remove_ids]
    return await set_transaction_tags(client, transaction_id, new_ids)
