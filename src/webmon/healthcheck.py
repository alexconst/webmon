from pydantic import BaseModel
from enum import Enum

class RegexMatchStatus(Enum):
    FAIL = 0
    OK = 1
    NA = 2

class Healthcheck(BaseModel):
    """A Pydantic model representing a website health check result.

    :param check_id: Defines datatype for primary key in datamodel.
    :param website_fk: Reference to Websites.
    :param request_timestamp: Timestamp when the request was initiated.
    :param response_time: The duration of time it took for a server to respond.
    :param http_status_code: HTTP status code of the health check.
    :param regex_match_status: Result of regex match.
    :param error_message: Details about encountered error when check is unsuccessful.
    """
    check_id: int
    website_fk: int
    request_timestamp: float
    response_time: float
    http_status_code: int
    regex_match_status: RegexMatchStatus
    error_message: str

