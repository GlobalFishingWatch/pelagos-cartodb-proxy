import json
import datetime
import os.path
import fcdjangoutils.cors
import fcdjangoutils.jsonview
import django.views.decorators.csrf
import django.http
from django.conf import settings
import vectortile.TypedMatrix
import vectortile.Bbox
import urllib
import tilegen
import slugify

@fcdjangoutils.cors.cors(headers = ['Origin', 'X-Requested-With', 'Content-Type', 'Accept', 'X-Client-Cache'])
def header(request, tileset):
    tileset = urllib.unquote(tileset)

    pathname = os.path.join(settings.MEDIA_ROOT, "tiles", slugify.slugify(unicode(tileset)))

    filename = os.path.join(pathname, "header")
    if not os.path.exists(pathname):
        os.makedirs(pathname)
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write(json.dumps(tilegen.load_header(tileset)))
    with open(filename) as f:
        res = django.http.HttpResponse(f.read(), content_type="text/json")
        res["Access-Control-Allow-Origin"] = "*"
        return res

@fcdjangoutils.cors.cors(headers = ['Origin', 'X-Requested-With', 'Content-Type', 'Accept', 'X-Client-Cache'])
def tile(request, tileset = None, time = None, bbox = None):
    tileset = urllib.unquote(tileset)

    pathname = os.path.join(settings.MEDIA_ROOT, "tiles", slugify.slugify(unicode(tileset)))

    filename = os.path.join(pathname, bbox)
    if not os.path.exists(pathname):
        os.makedirs(pathname)
    if not os.path.exists(filename) and not os.path.exists(filename + "-404"):
        tile = tilegen.load_tile(tileset, bbox=bbox)
        if tile is None:
            with open(filename + "-404", "w") as f:
                f.write("EMPTY")
        else:
            with open(filename, "w") as f:
                f.write(str(tile))
    if os.path.exists(filename + "-404"):
        res = django.http.HttpResponseNotFound("Tile is empty")
    else:
        with open(filename) as f:
            res = django.http.HttpResponse(f.read(), content_type="application/binary")
    res["Access-Control-Allow-Origin"] = "*"
    return res
