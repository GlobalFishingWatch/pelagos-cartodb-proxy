import json
import vectortile.TypedMatrix
import vectortile.Bbox
import vectortile.Tile
import urllib
import urllib2
import operator
import datetime

def load_url(url):
    try:
        return urllib2.urlopen(url)
    except urllib2.HTTPError as e:
        e.msg = e.read()
        raise e

def get_sql_url(layer, args):
    sql_url = layer["options"]["sql_api_template"].replace("{user}", layer["options"]["user_name"]) + layer["options"]["sql_api_endpoint"]

    if not args:
        return sql_url

    return "%s?%s" % (
        sql_url,
        "&".join(["%s=%s" % (name, urllib.quote(unicode(value)))
                  for name, value in args.iteritems()]))

def exec_sql(layer, **kw):
    try:
        return json.load(
            load_url(
                get_sql_url(layer, kw)))
    except urllib2.HTTPError as e:
        if "q" in kw:
            e.msg = "%s while executing %s" % (e.msg, kw["q"])
        raise e

def get_layer_fields(layer):
    return exec_sql(
        layer,
        page=0,
        sort_order="asc",
        order_by="",
        filter_column="",
        filter_value="",
        sql_source="null",
        limit=0,
        q=layer["options"]["sql"]
        )["fields"]

def get_layer_fields_sql(layer, filter = ["the_geom"]):
    return ",".join([name for name in layer["fields"].keys() if name not in filter])

def get_layer_data_sql(layer, bbox, **kw):
    return """
        select
          ST_Intersection(ST_MakeEnvelope(%(lonmin)s, %(latmin)s, %(lonmax)s, %(latmax)s, 4326), the_geom) the_geom,
          %(fields)s
        from
          (%(src)s) __wrapped__layer_data
        where
          ST_Contains(ST_MakeEnvelope(%(lonmin)s, %(latmin)s, %(lonmax)s, %(latmax)s, 4326), the_geom)
        order by
          cartodb_id asc
    """ % {"src": layer["options"]["sql"],
           "fields": get_layer_fields_sql(layer),
           "latmin": bbox.latmin,
           "latmax": bbox.latmax,
           "lonmin": bbox.lonmin,
           "lonmax": bbox.lonmax
           }

def get_layer_simplified_data_sql(layer, tolerance = None, **kw):
    if tolerance is None:
        return get_layer_data_sql(layer, **kw)
    return """
      select
        ST_Simplify(the_geom, %(tolerance)s, true),
        %(fields)s
      from
        (%(src)s) __wrapped__layer_simplified_data
    """ % {"src": get_layer_data_sql(layer, **kw),
           "fields": get_layer_fields_sql(layer)
           }


#   ST_Centroid(gc) AS centroid,
#   ST_MinimumBoundingCircle(gc) AS circle,
#   sqrt(ST_Area(ST_MinimumBoundingCircle(gc)) / pi()) AS radius
#   SELECT unnest(ST_ClusterWithin(geom, 100)) gc

def get_layer_data_points_sql(layer, **kw):
    return """
        select
          series,
          geometry_type,
          ST_Y(the_geom) lat,
          ST_X(the_geom) lon,
          %(fields)s
        from
          (select
             row_number() over () as series,
             ST_GeometryType(__wrapped__layer_data_points.the_geom) as geometry_type,
             (ST_DumpPoints(__wrapped__layer_data_points.the_geom)).geom as the_geom,
             %(fields)s
           from
             (%(src)s) __wrapped__layer_data_points
          ) __wrapped__layer_data_points_2
    """ % {
        "src": get_layer_simplified_data_sql(layer, **kw),
        "fields": get_layer_fields_sql(layer)
    }

def get_layer_data_size_sql(layer, **kw):
    return """
        select
          count(*) as size
        from
          (%s) as __wrapped_layer_data_size
    """ % (get_layer_data_points_sql(layer, **kw),)



def get_layer_data(layer, **kw):
    return exec_sql(
        layer,
        page=0,
        sort_order="asc",
        order_by="",
        filter_column="",
        filter_value="",
        sql_source="null",
        q=get_layer_data_points_sql(layer, **kw)
        )['rows']

def get_layer_data_size(layer, **kw):
    return exec_sql(
        layer,
        page=0,
        sort_order="asc",
        order_by="",
        filter_column="",
        filter_value="",
        sql_source="null",
        q=get_layer_data_size_sql(layer, **kw)
        )["rows"][0]["size"]

def find_layers(tileset_spec):
    layers = []
    def find_layers(obj, api_spec = {}):
        if "layers" not in obj: return
        for layer in obj["layers"]:
            if layer["type"] == "layergroup":
                api_spec = dict(api_spec)
                api_spec.update({key: value
                                for key, value in layer["options"].iteritems()
                                if key != "layers"})
                find_layers(layer["options"]["layer_definition"], api_spec)
            if layer["type"] == "CartoDB":
                layer["options"].update(api_spec)
                layers.append(layer)

    find_layers(tileset_spec)
    return layers

def load_tile(tileset = None, time = None, bbox = None):
    tileset = urllib.unquote(tileset)
    bbox = vectortile.Bbox.fromstring(bbox)

    tileset_spec = json.load(load_url(tileset))

    layers = find_layers(tileset_spec)

    for layer in layers:
        layer['fields'] = get_layer_fields(layer)
        print "LAYER SIZE", get_layer_data_size(layer, bbox=bbox)
        layer["data"] = get_layer_data(layer, bbox=bbox)

    def mangle_row(row):
        def mangle_value(key, value):
            if key in layer["fields"]:
                col = layer["fields"][key]
                if col["type"] == "number":
                    return value
                elif col["type"] == "date":
                    return (datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ") - datetime.datetime(1970, 1, 1)).total_seconds()
            if key in ["series", "lat", "lon"]:
                return value
            return None
        return {key: mangle_value(key, value)
                for key, value in row.iteritems()
                if mangle_value(key, value) is not None}

    data = [mangle_row(row)
            for row in reduce(operator.add,
                              [layer["data"] for layer in layers], [])]

    print "ROWS", len(data)
    tile = vectortile.Tile.fromdata(data)

    print "Tile made"
    with open("tile", "w") as f:
        f.write(str(tile))
    print "Tile saved"

load_tile(urllib.quote("http://cartodb.localhost:4711/user/dev/api/v2/viz/2cf0043c-97ba-11e5-87b3-0242ac110002/viz.json"), None, "0,0,90,90")
# load_tile(urllib.quote("http://cartodb.skytruth.org/user/dev/api/v2/viz/2cf0043c-97ba-11e5-87b3-0242ac110002/viz.json"), None, "0,0,90,90")
