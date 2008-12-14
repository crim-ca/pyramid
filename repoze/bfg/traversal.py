import urllib
import urlparse
   
from zope.interface import classProvides
from zope.interface import implements
from repoze.bfg.location import LocationProxy
from repoze.bfg.location import lineage

from repoze.bfg.interfaces import ILocation
from repoze.bfg.interfaces import ITraverser
from repoze.bfg.interfaces import ITraverserFactory

def split_path(path):
    while path.startswith('/'):
        path = path[1:]
    while path.endswith('/'):
        path = path[:-1]
    clean = []
    for segment in path.split('/'):
        segment = urllib.unquote(segment) # deal with spaces in path segment
        if not segment or segment=='.':
            continue
        elif segment == '..':
            del clean[-1]
        else:
            clean.append(segment)
    return clean

def step(ob, name, default):
    if name.startswith('@@'):
        return name[2:], default
    if not hasattr(ob, '__getitem__'):
        return name, default
    try:
        return name, ob[name]
    except KeyError:
        return name, default

_marker = ()

class ModelGraphTraverser(object):
    classProvides(ITraverserFactory)
    implements(ITraverser)
    def __init__(self, root):
        self.root = root
        self.locatable = ILocation.providedBy(root)

    def __call__(self, environ):
        path = environ.get('PATH_INFO', '/')
        path = split_path(path)
        ob = self.root

        name = ''

        while path:
            segment = path.pop(0)
            segment, next = step(ob, segment, _marker)
            if next is _marker:
                name = segment
                break
            if (self.locatable) and (not ILocation.providedBy(next)):
                next = LocationProxy(next, ob, segment)
            ob = next

        return ob, name, path

def find_root(model):
    """ Find the root node in the graph to which ``model``
    belongs. Note that ``model`` should be :term:`location`-aware.
    Note that the root node is available in the request object by
    accessing the ``request.root`` attribute.
    """
    for location in lineage(model):
        if location.__parent__ is None:
            model = location
            break
    return model

def find_model(model, path):
    """ Given a model object and a string representing a path
    reference (a set of names delimited by forward-slashes, such as
    the return value of ``model_path``), return an context in this
    application's model graph at the specified path.  If the path
    starts with a slash, the path is considered absolute and the graph
    traversal will start at the root object.  If the path does not
    start with a slash, the path is considered relative and graph
    traversal will begin at the model object supplied to the function.
    In either case, if the path cannot be resolved, a KeyError will be
    thrown. Note that the model passed in should be
    :term:`location`-aware."""

    if path.startswith('/'):
        model = find_root(model)
        
    ob, name, path = ITraverserFactory(model)({'PATH_INFO':path})
    if name:
        raise KeyError('%r has no subelement %s' % (ob, name))
    return ob

def find_interface(model, interface):
    """ Return the first object found which provides the interface
    ``interface`` in the parent chain of ``model`` or ``None`` if no
    object providing ``interface`` can be found in the parent chain.
    The ``model`` passed in should be :term:`location`-aware."""
    for location in lineage(model):
        if interface.providedBy(location):
            return location

def _urlsegment(s):
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    return urllib.quote(s)

def model_url(model, request, *elements):
    """ Return a string representing the absolute URL of the model
    object based on the ``wsgi.url_scheme``, ``HTTP_HOST`` or
    ``SERVER_NAME`` in the request, plus any ``SCRIPT_NAME``.  If any
    model in the lineage has a unicode name, it will be converted to
    UTF-8 before being attached to the URL.  Empty names in the model
    graph are ignored.

    Any positional arguments passed in as ``elements`` must be strings
    or unicode objects.  These will be joined by slashes and appended
    to the model URL.  Each of the elements passed in is URL-quoted
    before being appended; if any element is unicode, it will
    converted to a UTF-8 bytestring before being URL-quoted.

    If ``elements`` are not used, the model URL will end with a
    trailing slash.  If ``elements`` are used, the generated URL will
    *not* end in trailing a slash.

    The ``model`` passed in must be :term:`location`-aware.  The
    overall result of this function is always a string (never
    unicode). """
    rpath = []
    for location in lineage(model):
        name = location.__name__
        if name:
            rpath.append(_urlsegment(name))
    prefix = '/'.join(reversed(rpath))
    suffix = '/'.join([_urlsegment(s) for s in elements])
    path = '/'.join([prefix, suffix])
    app_url = request.application_url
    if not app_url.endswith('/'):
        app_url = app_url + '/'
    return urlparse.urljoin(app_url, path)

def model_path(model, *elements):
    """ Return a string representing the absolute path of the model
    object based on its position in the model graph, e.g
    ``/foo/bar``. Any positional arguments passed in as ``elements``
    will be joined by slashes and appended to the generated path.  The
    ``model`` passed in must be :term:`location`-aware.

    Note that this function is not equivalent to ``model_url``:
    individual segments in the path are not quoted in any way.  Thus,
    to ensure that this function generates paths that can later be
    resolved to models via ``find_model``, you should ensure that your
    model names do not contain any slashes.

    Note also that the path returned may be a Unicode string if any
    model name in the model graph is Unicode; otherwise it will be a
    byte-string."""
    rpath = []
    for location in lineage(model):
        if location.__name__:
            rpath.append(location.__name__)
    path = '/' + '/'.join(reversed(rpath))
    if elements: # never have a trailing slash
        suffix = '/'.join(elements)
        path = '/'.join([path, suffix])
    return path

