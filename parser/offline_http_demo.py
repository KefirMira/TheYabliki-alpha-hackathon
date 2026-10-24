"""Explicit offline HTTP/SQLite demo. Both RSS and backend transports are fake."""
import argparse
from contextlib import contextmanager
from io import BytesIO
import json
from pathlib import Path

import httpx

from .backend_client import BackendClient
from .collector import collect_once, save_report
from .config import Config, PARSER_DIR
from .http_source import HTTPRSS


def main(argv=None):
    cli=argparse.ArgumentParser(description='Offline synthetic HTTP RSS demo; no network and no AI')
    cli.add_argument('--once',action='store_true',required=True)
    cli.add_argument('--state-dir',type=Path,required=True)
    args=cli.parse_args(argv)
    config=Config.from_env({'PARSER_SOURCE_MODE':'http','PARSER_HTTP_RSS_ENABLED':'1',
        'PARSER_RSS_URL':'https://fixture.example.invalid/rss','PARSER_SOURCE_NAME':'synthetic-demo',
        'PARSER_STATE_PATH':str(args.state_dir.resolve()/'queue.sqlite3'),
        'PARSER_REPORT_PATH':str(args.state_dir.resolve()/'report.json')})
    @contextmanager
    def transport(url,ip,headers,timeout):
        class Response:
            status=304 if headers.get('If-None-Match')=='"synthetic-v1"' else 200
            body=BytesIO((PARSER_DIR/'fixtures/synthetic.xml').read_bytes())
            def getheader(self,name,default=None):
                return {'ETag':'"synthetic-v1"','Content-Type':'application/rss+xml; charset=utf-8'}.get(name,default)
            def read(self,size):return self.body.read(size)
        yield Response(),type('Connection',(),{'sock':None})()
    ids={}
    def deliver(request):
        payload=json.loads(request.content)
        key=payload.get('source_id') or payload['url']
        created=key not in ids
        ids.setdefault(key,len(ids)+1)
        return httpx.Response(201 if created else 200,json={'news_id':ids[key],
            'created':created,'duplicate':not created,'diagnostics':[]})
    with httpx.Client(transport=httpx.MockTransport(deliver),trust_env=False) as client:
        report=collect_once(config,BackendClient(config,client=client),
            fetch=HTTPRSS(transport=transport,resolver=lambda *args:['8.8.8.8']))
    save_report(config.report_path,report)
    print(json.dumps(report,ensure_ascii=False))
    return 1 if report['failed'] else 0


if __name__=='__main__':raise SystemExit(main())
