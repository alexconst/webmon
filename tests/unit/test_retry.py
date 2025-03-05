import asyncio
import logging
import os
import sys

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/'))
from webmon.retry import retry

# Set up a logger for the test
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

logger = None  # comment this to help with debugging


# Mock function to test the retry decorator
@retry(tries=3, delay=0.1, backoff=2, max_interval=1, logger=logger)
async def mock_function(should_fail=False, fail_count=0):
    if should_fail:
        if fail_count < 3:
            fail_count += 1
        else:
            raise Exception(f"Simulated failure {fail_count}")
    return f"Success after {fail_count} failures"


# Test cases
@pytest.mark.asyncio
async def test_retry_success():
    result = await mock_function(should_fail=False)
    assert result == "Success after 0 failures"


@pytest.mark.asyncio
async def test_retry_temporary_failure():
    result = await mock_function(should_fail=True, fail_count=0)
    assert result == "Success after 1 failures"


@pytest.mark.asyncio
async def test_retry_temporary_failure_2():
    result = await mock_function(should_fail=True, fail_count=1)
    assert result == "Success after 2 failures"


@pytest.mark.asyncio
async def test_retry_permanent_failure():
    result = None
    with pytest.raises(Exception):
        result = await mock_function(should_fail=True, fail_count=3)
    assert result is None
