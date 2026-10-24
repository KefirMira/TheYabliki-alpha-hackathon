"""Bounded RSS-only GET. DNS is validated and TCP connects to the pinned IP.

No proxies, cookies, authorization, article scraping or automatic HTTP retries.
"""
from contextlib import contextmanager
import codecs
import http.client
import ipaddress
import io
from queue import Queue, Empty
import re
import socket
import ssl
from threading import BoundedSemaphore, Thread
import time
from urllib.parse import urlsplit, urljoin
from xml.etree import ElementTree

from .backend_client import retry_after
from .rss import Item, CONTENT, clean_html, parse_date, MAX_XML_BYTES
from .models import NewsPayload
from .source import Scan
from pydantic import ValidationError


class SourceError(ValueError):
    def __init__(self, code, *, retryable=False, retry_at=None):
        self.code, self.retryable, self.retry_at = code, retryable, retry_at
        super().__init__(code)  # Never interpolate URL, XML or exception text.


def public_ip(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        raise SourceError('RSS_ADDRESS_DENIED') from None
    if (not ip.is_global or ip.is_multicast or ip.is_reserved
            or getattr(ip, 'ipv4_mapped', None) is not None or ip.is_unspecified
            or getattr(ip,'sixtofour',None) is not None or getattr(ip,'teredo',None) is not None):
        raise SourceError('RSS_ADDRESS_DENIED')
    return str(ip)


def parse_url(url):
    try:
        if not isinstance(url, str) or len(url)>2048 or any(ord(c)<=32 or ord(c)==127 for c in url) or '\\' in url:
            raise ValueError()
        p=urlsplit(url)
        if (p.scheme not in ('http','https') or not p.hostname or p.username is not None
                or p.password is not None or p.fragment or '%' in p.netloc):
            raise ValueError()
        host=p.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        port=p.port or (443 if p.scheme=='https' else 80)
        if port != (443 if p.scheme=='https' else 80):
            raise ValueError()
        if host=='localhost' or host.endswith(('.localhost','.local','.internal')) or '.' not in host:
            raise ValueError()
        # Numeric literals are allowed only if globally routable.
        try: ipaddress.ip_address(host)
        except ValueError:
            if re.fullmatch(r'[0-9.]+',host):raise ValueError()
        else: public_ip(host)
        return p,host,port
    except (ValueError,UnicodeError):
        raise SourceError('RSS_URL_DENIED') from None


_DNS_SLOTS=BoundedSemaphore(2)


def resolve(host,port,timeout):
    # Bound both waiting and the number of outstanding uninterruptible OS DNS calls.
    if not _DNS_SLOTS.acquire(blocking=False):
        raise SourceError('RSS_DNS_BUSY',retryable=True)
    result=Queue(maxsize=1)
    def lookup():
        try: result.put(socket.getaddrinfo(host,port,type=socket.SOCK_STREAM))
        except OSError: result.put(None)
        finally: _DNS_SLOTS.release()
    Thread(target=lookup,daemon=True).start()
    try: addresses=result.get(timeout=timeout)
    except Empty: raise SourceError('RSS_TIMEOUT',retryable=True) from None
    if not addresses: raise SourceError('RSS_NETWORK_ERROR',retryable=True)
    return [a[4][0] for a in addresses]


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self,host,port,ip,timeout):
        super().__init__(host,port,timeout=timeout)
        self.ip=ip

    def connect(self):
        self.sock=socket.create_connection((self.ip,self.port),timeout=self.timeout)


class PinnedHTTPS(PinnedHTTP):
    def connect(self):
        started=time.monotonic()
        super().connect()
        try:
            remaining=self.timeout-(time.monotonic()-started)
            if remaining<=0:raise TimeoutError()
            self.sock.settimeout(remaining)
            self.sock=ssl.create_default_context().wrap_socket(self.sock,server_hostname=self.host)
        except BaseException:
            self.sock.close()
            raise


class DeadlineSocket:
    """Bound slow headers/body too; http.client reads through makefile()."""
    def __init__(self,sock,deadline):
        self.sock,self.deadline=sock,deadline
        self.readers,self.closed=0,False

    def remaining(self):
        value=self.deadline-time.monotonic()
        if value<=0:raise TimeoutError()
        self.sock.settimeout(value)

    def sendall(self,data):
        self.remaining()
        self.sock.sendall(data)

    def makefile(self,mode):
        owner=self
        owner.readers+=1
        class Reader(io.RawIOBase):
            def readable(self):return True
            def readinto(self,buffer):
                owner.remaining()
                return owner.sock.recv_into(buffer)
            def close(self):
                if not self.closed:
                    owner.readers-=1
                    if owner.closed and owner.readers==0:owner.sock.close()
                super().close()
        return io.BufferedReader(Reader())

    def settimeout(self,value):self.sock.settimeout(value)
    def close(self):
        self.closed=True
        if self.readers==0:self.sock.close()


@contextmanager
def exchange(url,ip,headers,timeout):
    p,host,port=parse_url(url)
    connection=(PinnedHTTPS if p.scheme=='https' else PinnedHTTP)(host,port,ip,timeout)
    response=None
    try:
        deadline=time.monotonic()+timeout
        connection.connect()
        connection.sock=DeadlineSocket(connection.sock,deadline)
        target=(p.path or '/')+('?' + p.query if p.query else '')
        connection.request('GET',target,headers=headers)
        response=connection.getresponse()
        yield response,connection
    finally:
        if response is not None:response.close()
        connection.close()


def validator(value):
    if value is None: return None
    if len(value)>1024 or any(ord(c)<32 or ord(c)>126 for c in value):
        raise SourceError('RSS_INVALID_VALIDATOR')
    return value


def parse_http_rss(data,content_type,source_name):
    # Strict decoding; do not replace broken bytes with invented characters.
    match=re.search(r'charset\s*=\s*["\']?([a-zA-Z0-9._-]+)',content_type,re.I)
    declaration=re.search(br'<\?xml\s[^>]*encoding\s*=\s*["\']([^"\']+)',data[:256],re.I)
    try:
        encoding=match.group(1) if match else (declaration.group(1).decode('ascii') if declaration else 'utf-8-sig')
        canonical=codecs.lookup(encoding).name
        if canonical not in ('utf-8','utf-8-sig','cp1251','iso8859-1','ascii'):
            raise ValueError()
        if match and declaration and codecs.lookup(declaration.group(1).decode('ascii')).name.removesuffix('-sig') != canonical.removesuffix('-sig'):
            raise ValueError()
        xml=data.decode(encoding,errors='strict').lstrip('\ufeff')
    except (ValueError,LookupError,UnicodeError):
        raise SourceError('RSS_ENCODING_ERROR') from None
    if re.search(r'<!\s*(DOCTYPE|ENTITY)\b',xml,re.I):
        raise SourceError('RSS_UNSAFE_XML')
    try: root=ElementTree.fromstring(xml)
    except ElementTree.ParseError: raise SourceError('RSS_INVALID_XML') from None
    channel=root.find('channel')
    if root.tag!='rss' or root.get('version')!='2.0' or channel is None:
        raise SourceError('RSS_INVALID_XML')
    language=channel.findtext('language')
    language=language.strip() if language is not None else None
    items=[]
    for index,element in enumerate(channel.findall('item'),1):
        title=clean_html(element.findtext('title'))
        content=clean_html(element.findtext(CONTENT)) or clean_html(element.findtext('description'))
        guid=element.findtext('guid')
        guid=guid.strip() or None if guid is not None else None
        link=element.findtext('link')
        link=link.strip() or None if link is not None else None
        date,issues=parse_date(element.findtext('pubDate'))
        if not title or not content:
            items.append(Item(index,None,issues+['MISSING_TITLE' if not title else 'MISSING_CONTENT']))
            continue
        if guid is None and link is None:
            items.append(Item(index,None,issues+['NO_RELIABLE_IDENTITY']))
            continue
        try:
            payload=NewsPayload(title=title,content=content,url=link,source_name=source_name,
                                source_id=guid,published_at=date,language=language)
        except ValidationError as error:
            fields=sorted({str(e['loc'][0]) for e in error.errors()})
            items.append(Item(index,None,issues+['INVALID_FIELDS:'+','.join(fields)]))
        else: items.append(Item(index,payload,issues))
    return items


class HTTPRSS:
    def __init__(self, *, resolver=resolve, transport=exchange, clock=time.monotonic, wall_clock=time.time):
        self.resolver,self.transport,self.clock,self.wall_clock=resolver,transport,clock,wall_clock

    def __call__(self,config,conditional_headers):
        if not config.http_enabled or not config.rss_url:
            raise SourceError('RSS_HTTP_DISABLED')
        start=self.clock()
        p,host,port=parse_url(config.rss_url)
        origin=(p.scheme,host,port)
        url=config.rss_url
        headers={'User-Agent':'PulseBusinessRSS/1.16.0','Accept':'application/rss+xml, application/xml, text/xml',
                 'Accept-Encoding':'identity'}
        for name in ('If-None-Match','If-Modified-Since'):
            if conditional_headers.get(name) is not None:
                headers[name]=validator(conditional_headers[name])
        try:
            for hop in range(config.max_redirects+1):
                remaining=config.timeout-(self.clock()-start)
                if remaining<=0: raise SourceError('RSS_TIMEOUT',retryable=True)
                p,host,port=parse_url(url)
                if (p.scheme,host,port)!=origin:
                    raise SourceError('RSS_REDIRECT_DENIED')
                ips=self.resolver(host,port,remaining)
                if not ips:raise SourceError('RSS_NETWORK_ERROR',retryable=True)
                # Reject mixed public/private answers; never re-resolve in connect().
                ips=[public_ip(ip) for ip in ips]
                remaining=config.timeout-(self.clock()-start)
                if remaining<=0:raise SourceError('RSS_TIMEOUT',retryable=True)
                with self.transport(url,ips[0],headers,remaining) as (response,connection):
                    status=response.status
                    if status in (301,302,303,307,308):
                        location=response.getheader('Location')
                        if not location or hop==config.max_redirects:
                            raise SourceError('RSS_REDIRECT_DENIED')
                        url=urljoin(url,location)
                        # Validators belong to a resource, not just its origin.
                        headers.pop('If-None-Match',None)
                        headers.pop('If-Modified-Since',None)
                        continue
                    if status not in (200,304):
                        raise SourceError('RSS_HTTP_'+str(status),retryable=status==429 or 500<=status<=599,
                            retry_at=retry_after(response.getheader('Retry-After'),self.wall_clock()))
                    etag=validator(response.getheader('ETag'))
                    modified=validator(response.getheader('Last-Modified'))
                    if status==304:
                        if not any(name in headers for name in ('If-None-Match','If-Modified-Since')):
                            raise SourceError('RSS_UNSOLICITED_304')
                        return Scan(status=304,etag=etag,last_modified=modified)
                    if response.getheader('Content-Encoding','identity').lower()!='identity':
                        raise SourceError('RSS_ENCODING_UNSUPPORTED')
                    content_type=response.getheader('Content-Type','')
                    if content_type.split(';')[0].strip().lower() not in ('application/rss+xml','application/xml','text/xml'):
                        raise SourceError('RSS_CONTENT_TYPE_DENIED')
                    length=response.getheader('Content-Length')
                    if length is not None and (not length.isascii() or not length.isdigit() or int(length)>config.max_response_bytes):
                        raise SourceError('RSS_RESPONSE_TOO_LARGE')
                    data=bytearray()
                    while True:
                        remaining=config.timeout-(self.clock()-start)
                        if remaining<=0:raise SourceError('RSS_TIMEOUT',retryable=True)
                        if connection.sock is not None:connection.sock.settimeout(remaining)
                        chunk=response.read(min(16384,config.max_response_bytes+1-len(data)))
                        if not chunk:break
                        data.extend(chunk)
                        if len(data)>config.max_response_bytes:raise SourceError('RSS_RESPONSE_TOO_LARGE')
                    return Scan(items=parse_http_rss(bytes(data),content_type,config.source_name),
                        etag=etag if hop==0 else None,last_modified=modified if hop==0 else None)
        except SourceError:raise
        except TimeoutError:raise SourceError('RSS_TIMEOUT',retryable=True) from None
        except (OSError,http.client.HTTPException):raise SourceError('RSS_NETWORK_ERROR',retryable=True) from None
        except (ValueError,UnicodeError):raise SourceError('RSS_PROTOCOL_ERROR') from None
        raise SourceError('RSS_REDIRECT_DENIED')
