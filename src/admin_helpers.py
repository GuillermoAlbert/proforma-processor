import os
import functools
from flask import request, Response


def check_auth(username, password):
    return username == os.environ.get('ADMIN_USER', 'admin') and \
           password == os.environ.get('ADMIN_PASS', 'admin')


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response('Acceso denegado', 401,
                {'WWW-Authenticate': 'Basic realm="Proforma Admin"'})
        return f(*args, **kwargs)
    return decorated
