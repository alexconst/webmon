from pydantic import BaseModel

class Website(BaseModel):
    """A Pydantic model representing a website configuration.

    :param url: The url to check, eg: google.com, foobar.com:8080/health
    :param interval: The interval in seconds between checks or updates.
    :param regex: A regular expression used to match the content of a webpage.
    """
    url: str
    interval: int
    regex: str

