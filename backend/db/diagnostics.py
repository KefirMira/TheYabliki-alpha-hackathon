"""Allowlisted database diagnostics. Never serialize exception text or DSNs."""

def database_error_code(error):
    queue, seen = [error], set()
    timeout = False
    while queue:
        item = queue.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        state = getattr(item, 'sqlstate', None) or getattr(item, 'pgcode', None)
        if state in {'28P01', '28000'}:
            return 'DATABASE_AUTHENTICATION_FAILED'
        if state == '3D000':
            return 'DATABASE_NOT_FOUND'
        if state == '42501':
            return 'DATABASE_PERMISSION_DENIED'
        timeout = timeout or isinstance(item, TimeoutError)
        for name in ('orig', '__cause__', '__context__'):
            child = getattr(item, name, None)
            if isinstance(child, BaseException):
                queue.append(child)
    return 'DATABASE_TIMEOUT' if timeout else 'DATABASE_UNAVAILABLE'
