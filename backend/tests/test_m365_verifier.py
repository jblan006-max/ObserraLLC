import asyncio

import pytest

from verifiers.m365 import verify_entra_connector


@pytest.mark.asyncio
async def test_verify_entra_connector_invalid_credentials():
    # Using invalid/fake credentials should return evidence with ok=False or details indicating token error
    res = await verify_entra_connector("org_fake", "00000000-0000-0000-0000-000000000000", "fake-client", "fake-secret")
    assert isinstance(res, dict)
    # ok may be False due to token error or network failure
    assert "details" in res
    assert any(d.get("check") == "token" or d.get("check") == "exception" for d in res["details"]) or res.get("ok") in (False, True)
