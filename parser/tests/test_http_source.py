from contextlib import contextmanager
from io import BytesIO
from types import SimpleNamespace
import socket

import pytest

from parser.http_source import HTTPRSS, SourceError, parse_http_rss, PinnedHTTP, parse_url

XML=b'''<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><language>ru</language>
<item><guid>SYNTH-HTTP-1</guid><title>Synthetic</title><description>&lt;p&gt;Text &amp;amp; fact&lt;/p&gt;</description>
<link>https://example.invalid/news/1</link><pubDate>Thu, 01 Jan 2026 12:00:00 +0300</pubDate></item>
<item><guid>SYNTH-HTTP-1</guid><title>Duplicate</title><description>Same identity</description></item>
<item><guid>SYNTH-MISSING</guid><title>No text</title></item></channel></rss>'''


def config(**kwargs):
    return SimpleNamespace(**dict({'http_enabled':True,'rss_url':'https://feed.example.invalid/rss',
        'source_name':'synthetic-demo','timeout':2,'max_redirects':2,'max_response_bytes':1048576},**kwargs))


class FakeResponse:
    def __init__(self,status=200,body=XML,headers=None):
        self.status=status
        self.body=BytesIO(body)
        self.headers={'Content-Type':'application/rss+xml',**(headers or {})}
    def getheader(self,name,default=None):return self.headers.get(name,default)
    def read(self,size):return self.body.read(size)


class Transport:
    def __init__(self,*responses):self.responses=iter(responses);self.calls=[]
    @contextmanager
    def __call__(self,url,ip,headers,timeout):
        self.calls.append((url,ip,dict(headers),timeout))
        response=next(self.responses)
        if isinstance(response,Exception):raise response
        yield response,SimpleNamespace(sock=None)


def adapter(transport,addresses=None):
    return HTTPRSS(transport=transport,resolver=lambda *args:addresses or ['8.8.8.8'],wall_clock=lambda:1000)


def test_http_success_and_validators():
    transport=Transport(FakeResponse(headers={'ETag':'"v1"','Last-Modified':'Thu, 01 Jan 2026 09:00:00 GMT'}))
    scan=adapter(transport)(config(),{'If-None-Match':'"old"'})
    assert scan.etag=='"v1"' and scan.last_modified
    assert scan.items[0].payload.content=='Text & fact'
    assert scan.items[0].payload.published_at.isoformat()=='2026-01-01T09:00:00+00:00'
    assert scan.items[0].payload.source_name=='synthetic-demo'
    assert scan.items[1].payload.source_id==scan.items[0].payload.source_id
    assert scan.items[2].payload is None
    assert transport.calls[0][1]=='8.8.8.8'
    assert transport.calls[0][2]['If-None-Match']=='"old"'
    assert transport.calls[0][2]['Accept-Encoding']=='identity'


def test_http_304_does_not_read_body():
    response=FakeResponse(304,headers={'ETag':'"new"'})
    response.read=lambda *args:pytest.fail('304 must not consume/parse a body')
    scan=adapter(Transport(response))(config(),{'If-None-Match':'"v1"','If-Modified-Since':'date'})
    assert scan.status==304 and scan.items==[] and scan.etag=='"new"'


@pytest.mark.parametrize('status',[429,500,503])
def test_temporary_error_and_retry_after(status):
    with pytest.raises(SourceError) as error:
        adapter(Transport(FakeResponse(status,headers={'Retry-After':'120'})))(config(),{})
    assert error.value.retryable and error.value.retry_at==1120
    assert str(error.value)=='RSS_HTTP_'+str(status)


@pytest.mark.parametrize('response,code',[
    (TimeoutError('secret network details'),'RSS_TIMEOUT'),
    (OSError('secret network details'),'RSS_NETWORK_ERROR'),
    (FakeResponse(body=b'x'*101),'RSS_RESPONSE_TOO_LARGE'),
    (FakeResponse(headers={'Content-Length':'999999'}),'RSS_RESPONSE_TOO_LARGE'),
    (FakeResponse(body=b'<rss>'),'RSS_INVALID_XML'),
    (FakeResponse(body=b'\xff'),'RSS_ENCODING_ERROR'),
    (FakeResponse(headers={'Content-Encoding':'gzip'}),'RSS_ENCODING_UNSUPPORTED'),
    (FakeResponse(headers={'Content-Type':'text/html'}),'RSS_CONTENT_TYPE_DENIED'),
    (FakeResponse(304),'RSS_UNSOLICITED_304'),
    (FakeResponse(headers={'ETag':'secret\r\ninjected'}),'RSS_INVALID_VALIDATOR'),
])
def test_failures_are_bounded_and_sanitized(response,code):
    with pytest.raises(SourceError) as error:adapter(Transport(response))(config(max_response_bytes=100),{})
    assert error.value.code==code and 'secret' not in str(error.value)


@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','192.168.0.1','172.16.0.1','169.254.169.254','0.0.0.0',
    '::1','fe80::1','fc00::1','::ffff:8.8.8.8','224.0.0.1',
    '2002:0a00:0001::1','2001:0000:4136:e378:8000:63bf:3fff:fdd2'])
def test_dns_private_and_mixed_answers_denied(ip):
    transport=Transport()
    with pytest.raises(SourceError):adapter(transport,['8.8.8.8',ip])(config(),{})
    assert not transport.calls


@pytest.mark.parametrize('url',['http://localhost/rss','http://127.0.0.1/rss','http://169.254.169.254/',
    'https://user:secret@feed.example.invalid/rss','file:///rss','https://feed.example.invalid:8443/rss',
    'https://feed.example.invalid/\r\nsecret','http://2130706433/rss','http://127.1/rss'])
def test_unsafe_url_denied(url):
    with pytest.raises(SourceError):parse_url(url)


@pytest.mark.parametrize('location',['http://127.0.0.1/rss','http://feed.example.invalid/rss',
    'https://other.example.invalid/rss','https://user:secret@feed.example.invalid/rss'])
def test_redirects_cannot_escape_origin(location):
    transport=Transport(FakeResponse(302,headers={'Location':location}))
    with pytest.raises(SourceError):adapter(transport)(config(),{})
    assert len(transport.calls)==1


def test_same_origin_redirect_and_rebinding_check():
    transport=Transport(FakeResponse(302,headers={'Location':'/next'}),FakeResponse(headers={'ETag':'"target"'}))
    scan=adapter(transport)(config(),{'If-None-Match':'"original"'})
    assert scan.items and scan.etag is None
    assert transport.calls[1][0]=='https://feed.example.invalid/next'
    assert 'If-None-Match' not in transport.calls[1][2]
    calls=iter([['8.8.8.8'],['127.0.0.1']])
    transport=Transport(FakeResponse(302,headers={'Location':'/next'}))
    with pytest.raises(SourceError):HTTPRSS(transport=transport,resolver=lambda *args:next(calls))(config(),{})
    assert len(transport.calls)==1


def test_connection_pins_ip_without_resolving_host_again(monkeypatch):
    calls=[]
    monkeypatch.setattr(socket,'create_connection',lambda target,timeout:calls.append(target) or object())
    connection=PinnedHTTP('feed.example.invalid',80,'8.8.8.8',2)
    connection.connect()
    assert calls==[('8.8.8.8',80)]


def test_cp1251_and_conflicting_encoding():
    xml=XML.decode().replace('utf-8','windows-1251').replace('Synthetic','Синтетика')
    assert parse_http_rss(xml.encode('cp1251'),'application/rss+xml; charset=windows-1251','test')[0].payload.title=='Синтетика'
    with pytest.raises(SourceError,match='ENCODING_ERROR'):
        parse_http_rss(xml.encode('cp1251'),'text/xml; charset=utf-8','test')


def test_real_loopback_socket_handles_connection_close_and_large_body():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    import time
    from parser.http_source import DeadlineSocket
    body=b'x'*40000
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    connection=PinnedHTTP('fixture.example.invalid',server.server_port,'127.0.0.1',2)
    try:
        connection.connect()
        connection.sock=DeadlineSocket(connection.sock,time.monotonic()+2)
        connection.request('GET','/')
        response=connection.getresponse()  # HTTP/1.0 closes connection, file must remain readable.
        assert response.read()==body
        response.close()
    finally:
        connection.close()
        server.shutdown();server.server_close();worker.join(timeout=3)


def test_offline_http_demo_uses_no_real_network(tmp_path,capsys):
    from parser.offline_http_demo import main
    assert main(['--once','--state-dir',str(tmp_path)])==0
    assert main(['--once','--state-dir',str(tmp_path)])==0
    import json
    reports=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert reports[0]['queue_counts']=={'delivered':6}
    assert reports[1]['counts']=={'already_delivered':6}


def test_redirect_loop_is_bounded():
    transport=Transport(*(FakeResponse(302,headers={'Location':'/again'}) for _ in range(3)))
    with pytest.raises(SourceError,match='REDIRECT_DENIED'):adapter(transport)(config(),{})
    assert len(transport.calls)==3


def test_invalid_conditional_validator_is_not_sent():
    transport=Transport()
    with pytest.raises(SourceError,match='INVALID_VALIDATOR'):
        adapter(transport)(config(),{'If-None-Match':'secret\r\nheader'})
    assert not transport.calls
