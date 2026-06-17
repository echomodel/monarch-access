"""Attach a file (receipt, check image, statement PDF) to a transaction.

Three-step flow, verified against the live Monarch web app:

  1. ``getTransactionAttachmentUploadInfo(transactionId)`` -> signed
     Cloudinary upload params (path + timestamp/folder/signature/api_key/
     upload_preset).
  2. multipart POST the file bytes to Cloudinary (signature-authed; no
     Monarch token) -> ``public_id``, ``format`` (extension), ``bytes``.
  3. ``addTransactionAttachment(input)`` -> links the asset to the
     transaction and returns the attachment record.

Monarch supports MULTIPLE attachments per transaction, so call this once
per file (e.g. check front, check back, an invoice).
"""

import os
from typing import Optional

from ..client import APIError
from ..queries import (
    ADD_TRANSACTION_ATTACHMENT_MUTATION,
    GET_TRANSACTION_ATTACHMENT_UPLOAD_INFO_MUTATION,
)


async def attach_transaction_bytes(
    client,
    transaction_id: str,
    file_bytes: bytes,
    upload_name: str,
    filename: Optional[str] = None,
) -> dict:
    """Attach raw bytes to a transaction. ``upload_name`` is the source
    filename (used for the multipart part + to derive the extension);
    ``filename`` is the display name shown in Monarch (defaults to
    ``upload_name`` without its extension)."""
    display_name = filename or os.path.splitext(upload_name)[0]

    # Step 1 — signed Cloudinary upload params for this transaction.
    data = await client._request(
        GET_TRANSACTION_ATTACHMENT_UPLOAD_INFO_MUTATION,
        {"transactionId": transaction_id},
    )
    info = (data.get("getTransactionAttachmentUploadInfo") or {}).get("info") or {}
    path = info.get("path")
    params = info.get("requestParams") or {}
    if not path or not params:
        raise APIError(
            f"No attachment upload info returned for transaction {transaction_id}"
        )

    # Step 2 — upload the bytes to Cloudinary (signature-authed).
    cl = await client.cloudinary_upload(path, params, file_bytes, upload_name)
    public_id = cl.get("public_id")
    if not public_id:
        raise APIError(f"Cloudinary upload returned no public_id: {str(cl)[:200]}")

    # Step 3 — link the uploaded asset to the transaction.
    variables = {
        "input": {
            "transactionId": transaction_id,
            "filename": display_name,
            "publicId": public_id,
            "extension": cl.get("format"),
            "sizeBytes": cl.get("bytes"),
        }
    }
    d2 = await client._request(ADD_TRANSACTION_ATTACHMENT_MUTATION, variables)
    result = d2.get("addTransactionAttachment", {})
    if result.get("errors"):
        raise APIError(f"Attach failed: {result['errors']}")
    return result.get("attachment", {})


async def attach_transaction_file(
    client,
    transaction_id: str,
    file_path: str,
    filename: Optional[str] = None,
) -> dict:
    """Read a local file and attach it to a transaction."""
    if not os.path.isfile(file_path):
        raise APIError(f"File not found: {file_path}")
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    return await attach_transaction_bytes(
        client, transaction_id, file_bytes, os.path.basename(file_path), filename
    )
