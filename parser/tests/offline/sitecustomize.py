"""Test-only startup guard, also injected into CLI subprocesses via PYTHONPATH."""
import ipaddress
import os
import socket
import sys

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
for key in ('LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL'):
    os.environ.pop(key, None)
for sdk in ('openai', 'anthropic', 'google.generativeai'):
    sys.modules[sdk] = None


def allowed(host):
    if isinstance(host, bytes):
        host = host.decode('ascii')
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
original_getaddrinfo = socket.getaddrinfo
original_sendto = socket.socket.sendto


def connect(self, address):
    if not isinstance(address, tuple) or not allowed(address[0]):
        raise AssertionError('External network blocked by parser test guard')
    return original_connect(self, address)


def connect_ex(self, address):
    if not isinstance(address, tuple) or not allowed(address[0]):
        raise AssertionError('External network blocked by parser test guard')
    return original_connect_ex(self, address)


def getaddrinfo(host, *args, **kwargs):
    if not allowed(host):
        raise AssertionError('External DNS blocked by parser test guard')
    return original_getaddrinfo(host, *args, **kwargs)


def sendto(self, data, *args):
    address = args[-1]
    if not isinstance(address, tuple) or not allowed(address[0]):
        raise AssertionError('External network blocked by parser test guard')
    return original_sendto(self, data, *args)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
socket.socket.sendto = sendto
