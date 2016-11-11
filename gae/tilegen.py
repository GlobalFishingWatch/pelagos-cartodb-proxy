import json
import vectortile.TypedMatrix
import vectortile.Bbox
import vectortile.Tile
import urllib
import urllib2
import operator
import datetime
import json
import sys
import re

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
    args = dict(
        page=0,
        sort_order="asc",
        order_by="",
        filter_column="",
        filter_value="",
        sql_source="null"
        )
    args.update(kw)
    if 'q' in args:
        args['q'] = re.sub("  +", " ", args['q'])
    try:
        return json.load(
            load_url(
                get_sql_url(layer, args)))
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

def get_layer_fields_list(layer, filter = ["the_geom"], func = None, types = ["date", "number"]):
    fields = layer["fields"].keys()
    fields = [name for name in fields if name not in filter]
    if types is not None:
        fields = [name for name in fields if
                  layer["fields"][name]["type"] in types]
    if func:
        fields = ["%s as %s" % (func(name), name) for name in fields]
    return fields

def get_layer_fields_sql(*arg, **kw):
    return ",".join(get_layer_fields_list(*arg, **kw))

def get_layer_data_sql(layer, bbox, **kw):
    series_group_sql = ""
    if "series_group" not in layer["fields"]:
        series_group_sql = "row_number() over () as series_group,"

    def convert_col(name):
        if layer["fields"][name]["type"] == "date":
            return "extract(epoch from %s at time zone 'utc')" % name
        return name

    return """
        select
          %(series_group_sql)s
          (ST_Dump(ST_Intersection(ST_MakeEnvelope(%(lonmin)s, %(latmin)s, %(lonmax)s, %(latmax)s, 4326), the_geom))).geom as the_geom,
          %(fields)s
        from
          (%(src)s) __wrapped__layer_data
        where
          ST_Contains(ST_MakeEnvelope(%(lonmin)s, %(latmin)s, %(lonmax)s, %(latmax)s, 4326), the_geom)
        order by
          cartodb_id asc
    """ % {"src": layer["options"]["sql"],
           "series_group_sql": series_group_sql,
           "fields": get_layer_fields_sql(layer, func=convert_col),
           "latmin": bbox.latmin,
           "latmax": bbox.latmax,
           "lonmin": bbox.lonmin,
           "lonmax": bbox.lonmax
           }

def get_layer_simplified_data_sql(layer, tolerance = None, **kw):
    series_group_sql = ""
    if "series_group" not in layer["fields"]:
        series_group_sql = "series_group,"
    if tolerance is None:
        return get_layer_data_sql(layer, **kw)
    return """
      select
        %(series_group_sql)s
        ST_SimplifyPreserveTopology(the_geom, %(tolerance)s) the_geom,
        %(fields)s
      from
        (%(src)s) __wrapped__layer_simplified_data
    """ % {"src": get_layer_data_sql(layer, **kw),
           "series_group_sql": series_group_sql,
           "fields": get_layer_fields_sql(layer),
           "tolerance": tolerance
           }


#   ST_Centroid(gc) AS centroid,
#   ST_MinimumBoundingCircle(gc) AS circle,
#   sqrt(ST_Area(ST_MinimumBoundingCircle(gc)) / pi()) AS radius
#   SELECT unnest(ST_ClusterWithin(geom, 100)) gc

def get_layer_data_points_sql(layer, **kw):
    series_sql = ""
    if "series" not in layer["fields"]:
        series_sql = "row_number() over () as series,"
    series_group_sql = ""
    if "series_group" not in layer["fields"]:
        series_group_sql = "series_group,"
    return """
        select
          %(series_group_sql)s
          %(series_sql)s
          (ST_DumpPoints(__wrapped__layer_data_points.the_geom)).geom as the_geom,
          %(fields)s
        from
          (%(src)s) __wrapped__layer_data_points
    """ % {
        "src": get_layer_simplified_data_sql(layer, **kw),
        "series_group_sql": series_group_sql,
        "series_sql": series_sql,
        "fields": get_layer_fields_sql(layer)
    }

def get_layer_data_clustered_points_sql(layer, hashlen=None, **kw):
    if hashlen is None:
        return get_layer_data_points_sql(layer, **kw)
    return """
      select
        100000 + row_number() over () AS series_group,
        100000 + row_number() over () AS series,
        ST_Centroid(ST_GeomFromGeoHash(geo_hash)) the_geom,
        %(filtered_fields)s
      from
        (select
           ST_GeoHash(the_geom, %(hashlen)s) as geo_hash,
           %(avg_fields)s
         from
           (%(src)s) __wrapped__layer_data_clustered_points_1
         group by
           ST_GeoHash(the_geom, %(hashlen)s)
        ) __wrapped__layer_data_clustered_points
    """ % {
        "src": get_layer_simplified_data_sql(layer, **kw),
        "hashlen": hashlen,
        "filtered_fields": get_layer_fields_sql(layer, filter=("sigma", "weight", "series", "series_group")),
        "avg_fields": get_layer_fields_sql(layer, func=lambda name: "avg(%s)" % name)
    }


def get_layer_data_points_lat_lon_sql(layer, **kw):
    series_sql = ""
    if "series" not in layer["fields"]:
        series_sql = "series,"
    series_group_sql = ""
    if "series_group" not in layer["fields"]:
        series_group_sql = "series_group,"
    return """
        select
          %(series_group_sql)s
          %(series_sql)s
          ST_Y(the_geom) latitude,
          ST_X(the_geom) longitude,
          %(fields)s
        from
          (%(src)s) __wrapped__layer_data_points_lat_lng
    """ % {
        "src": get_layer_data_clustered_points_sql(layer, **kw),
        "series_group_sql": series_group_sql,
        "series_sql": series_sql,
        "fields": get_layer_fields_sql(layer)
    }

def get_layer_data_size_sql(layer, **kw):
    return """
        select
          count(*) as size
        from
          (%s) as __wrapped_layer_data_size
    """ % (get_layer_data_clustered_points_sql(layer, **kw),)

def get_layer_data_max_geometry_size_sql(layer, **kw):
    return """
        select
          max(ST_NPoints(the_geom)) as size
        from
          (%s) as __wrapped_layer_data_max_geometry_size
    """ % (get_layer_simplified_data_sql(layer, **kw),)

def get_layer_data(layer, **kw):
    return exec_sql(
        layer,
        q=get_layer_data_points_lat_lon_sql(layer, **kw)
        )['rows']

def get_layer_data_size(layer, **kw):
    return exec_sql(
        layer,
        q=get_layer_data_size_sql(layer, **kw)
        )["rows"][0]["size"]

def get_layer_data_max_geometry_size(layer, **kw):
    return exec_sql(
        layer,
        q=get_layer_data_max_geometry_size_sql(layer, **kw)
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

def load_tile(tileset = None, time = None, bbox = None, max_size = 16000, **kw):
    bbox = vectortile.Bbox.fromstring(bbox)

    tileset_spec = json.load(load_url(tileset))

    layers = find_layers(tileset_spec)

    cluster_methods = set()

    print "LAYERS", len(layers)

    for layer in layers:
        layer['fields'] = get_layer_fields(layer)
        print "LAYER SIZE", get_layer_data_size(layer, bbox=bbox)
        print "LAYER MAX GEOM SIZE", get_layer_data_max_geometry_size(layer, bbox=bbox)

        options = dict(bbox=bbox)

        while True:
            size = get_layer_data_size(layer, **options)
            print "size %s at %s" % (size, options)
            if size < max_size: break
            if "tolerance" not in options:
                cluster_methods.add("st_simplify")
                options["tolerance"] = 1e-3
                continue
            geom_size = get_layer_data_max_geometry_size(layer, **options)
            if geom_size > 2:
                print "geom size %s at %s" % (size, options)
                options["tolerance"] *= 10.0
                continue
            if "hashlen" not in options:
                cluster_methods.add("geohash")
                options["hashlen"] = 20
                continue
            options["hashlen"] -= 1
            if options["hashlen"] <= 0:
                break

        layer["data"] = get_layer_data(layer, **options)

    data = reduce(operator.add,
                  [layer["data"] for layer in layers], [])

    for row in data:
        for name in ('latitude', 'longitude', 'series', 'series_group', 'weight', 'sigma'):
            if name not in row:
                row[name] = 0.0
    
    print "ROWS", len(data)

    meta = {
        "tags": list(cluster_methods),
        "series": len(set((row["series"] for row in data)))
        }

    if len(data):
        return vectortile.Tile.fromdata(data, meta)
    else:
        return None

def load_header(tileset, **kw):
    tileset_spec = json.load(load_url(tileset))

    layers = find_layers(tileset_spec)

    fields = set()
    for layer in layers:
        layer['fields'] = get_layer_fields(layer)
        fields.update(get_layer_fields_list(layer))

    for name in ('latitude', 'longitude', 'series', 'series_group', 'weight', 'sigma'):
        fields.add(name)

    return {
        "tilesetName": tileset_spec["title"],
        "seriesTilesets": False,
        "infoUsesSelection": True,
        "colsByName": {name: {"type": "Float32"}
                       for name in fields}
        }

if __name__ == "__main__":
    args = []
    kws = {"max_size": "16000"}
    for arg in sys.argv[1:]:
        if arg.startswith('--'):
            arg = arg[2:]
            value = True
            if '=' in arg:
                arg, value = arg.split('=')
            kws[arg] = value
        else:
            args.append(arg)

    kws["max_size"] = int(kws["max_size"])
    
    if not args:
        print """Usages:
    tilegen.py tile [--max_size=16000] http://cartodb.localhost:4711/user/dev/api/v2/viz/2cf0043c-97ba-11e5-87b3-0242ac110002/viz.json 0,0,90,90 mytile
    tilegen.py header http://cartodb.localhost:4711/user/dev/api/v2/viz/2cf0043c-97ba-11e5-87b3-0242ac110002/viz.json myheader
"""
    elif args[0] == "tile":
        viz, bbox, filename = args[1:]

        tile = load_tile(viz, bbox=bbox, **kws)

        with open(filename, "w") as f:
            f.write(str(tile))
    elif args[0] == "header":
        viz, filename = args[1:]
        header = load_header(viz, **kws)
        with open(filename, "w") as f:
            f.write(json.dumps(header))

