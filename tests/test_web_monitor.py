import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/'))
from webmon.web_monitor import WebMonitor

def test_get_valid_url():
    assert WebMonitor.get_valid_url('foo.com') == 'https://foo.com:443'
    assert WebMonitor.get_valid_url('foo42.com') == 'https://foo42.com:443'
    assert WebMonitor.get_valid_url('foo.com:8080') == 'http://foo.com:8080'
    assert WebMonitor.get_valid_url('foo.io/health') == 'https://foo.io:443/health'
    assert WebMonitor.get_valid_url('foo.com:8080/health') == 'http://foo.com:8080/health'


