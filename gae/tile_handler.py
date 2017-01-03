import virtualenvloader
import urllib
import urllib2
import config
import json
import tilegen
import slugify
import corshandler
import gcsupload
import webapp2
import googleapi
import logging

class GCSCache(object):
    """Caches files on GCS. Returns redirect tiles for cache
    matches."""

    def __init__(self, tileset, tile_version = '0.0'):
        """
        :param tileset: name of the tileset for this cache.
        :param tile_version: version number for tiles in this tileset.
        All keys must be unique within the tileset and version
        """
        self.tileset = tileset
        self.tile_version = tile_version
        self.namespace =  '%s/%s' % (self.encode(self.tileset), self.encode(self.tile_version))

    def encode(self, s):
        if isinstance(s, str):
            return s
        return unicode(s).encode('utf-8')

    def check(self, key):
        path = '%s/%s/%s' % (config.TILESET_FOLDER, self.namespace, self.encode(key))
        data = googleapi.storage.objects().list(bucket=config.TILESET_BUCKET,
                                                prefix=path,
                                                delimiter="/").execute()
        # print "CHEK", path, ('items' in data and data['items'])
        if 'items' in data and data['items']:
            matches = [item
                       for item in data['items']
                       if item["name"] == path]
            if matches:
                return path

        return None

    def redirect_url(self, key):
        return config.TILESET_URL + "/" + self.namespace + "/" + self.encode(key)

    def get(self, key):
        hit = self.check(key)
        if hit:
            logging.info("Cache Hit for Tile %s: %s" % (key, hit))
            return self.redirect_url(key)
        else:
            logging.info("Cache Miss for Tile %s" % key)
            return None

    def set(self, key, data):
        logging.info("Caching data %s" % key)
        gcsupload.upload(googleapi.storage, data, config.TILESET_BUCKET, config.TILESET_FOLDER + "/" + self.namespace + "/" + key)
        return self.redirect_url(key)


def cache(self, tileset, version, key, do_cache = True):
    cache = GCSCache(slugify.slugify(unicode(tileset)), version)
    def proxy_url(url):
        conn = urllib2.urlopen(url)
        self.response.headers['Cache-Control'] = 'max-age=31556926'
        self.response.headers['Content-Type'] = conn.info()['Content-type']
        self.response.write(conn.read())
    def wrapper(fn):
        if not do_cache or config.TEST_SERVER or config.LOCAL_TILESETS:
            self.response.write(fn())
        else:
            url = cache.get(key)
            if url:
                return proxy_url(url)
            url = cache.get(key + "-404")
            if url:
                self.response.headers['Cache-Control'] = 'max-age=31556926'
                self.response.status = 404
                return
            data = fn()
            if data is not None:
                url = cache.set(key, data)
                return proxy_url(url)
            cache.set(key + "-404", "EMPTY")
            self.response.headers['Cache-Control'] = 'max-age=31556926'
            self.response.status = 404
    return wrapper


class HeaderHandler(corshandler.CORSHandler):
    def get(self, tileset, version):
	logging.info("XXXX header %s/%s" % (tileset, version))

        tileset = urllib.unquote(tileset)

        @cache(self, tileset, version, "header")
        def generate_header():
            return json.dumps(tilegen.load_header(tileset))

class InfoHandler(corshandler.CORSHandler):
    def get(self, tileset, version):
	logging.info("XXXX header %s/%s" % (tileset, version))

        tileset = urllib.unquote(tileset)

        @cache(self, tileset, version, "info")
        def generate_info():
            return json.dumps(tilegen.load_info(tileset))

class TileHandler(corshandler.CORSHandler):
    def get(self, tileset, version, time = None, bbox = None):
	logging.info("XXXX tile %s/%s %s;%s" % (tileset, version, time, bbox))
        tileset = urllib.unquote(tileset)

        @cache(self, tileset, version, bbox, do_cache=False)
        def generate_tile():
            tile = tilegen.load_tile(tileset, bbox=bbox)
            if tile is not None:
                tile = str(tile)
            return tile

app = webapp2.WSGIApplication([
    webapp2.Route('/tile/<tileset:.*>/<version>/header', handler=HeaderHandler),
    webapp2.Route('/tile/<tileset:.*>/<version>/info', handler=InfoHandler),
    webapp2.Route('/tile/<tileset:.*>/<version>/<time>;<bbox>', handler=TileHandler),
    webapp2.Route('/tile/<tileset:.*>/<version>/<bbox>', handler=TileHandler)
], debug=True)
