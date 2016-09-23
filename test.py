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
    args = dict(
        page=0,
        sort_order="asc",
        order_by="",
        filter_column="",
        filter_value="",
        sql_source="null"
        )
    args.update(kw)
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

def get_layer_fields_sql(layer, filter = ["the_geom"]):
    return ",".join([name for name in layer["fields"].keys() if name not in filter])

def get_layer_data_sql(layer, bbox, **kw):
    series_group_sql = ""
    if "series_group" not in layer["fields"]:
        series_group_sql = "row_number() over () as series_group,"
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
           "fields": get_layer_fields_sql(layer),
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
          ST_GeometryType(__wrapped__layer_data_points.the_geom) as geometry_type,
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

def get_layer_data_clustered_points_sql(layer, radius=None, **kw):
    if radius is None:
        return get_layer_data_points_sql(layer, **kw)
    return """
        select
          100000 + row_number() over () AS series_group,
          100000 + row_number() over () AS series,
          ST_Centroid(gc) AS the_geom,
          ST_NumGeometries(gc) as weight,
          sqrt(ST_Area(ST_MinimumBoundingCircle(gc)) / pi()) AS sigma,
          %(filtered_fields)s
        from
          (select
             unnest(ST_ClusterWithin(the_geom, %(radius)s)) gc,
             %(fields)s
           from
             (%(src)s) __wrapped__layer_data_clustered_points_1
          ) __wrapped__layer_data_clustered_points_2
    """ % {
        "src": get_layer_simplified_data_sql(layer, **kw),
        "radius": radius,
        "filtered_fields": get_layer_fields_sql(layer, filter=("sigma", "weight", "series", "series_group")),
        "fields": get_layer_fields_sql(layer)
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
          geometry_type,
          ST_Y(the_geom) lat,
          ST_X(the_geom) lon,
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

def load_tile(tileset = None, time = None, bbox = None, max_size = 100):
    tileset = urllib.unquote(tileset)
    bbox = vectortile.Bbox.fromstring(bbox)

    tileset_spec = json.load(load_url(tileset))

    layers = find_layers(tileset_spec)

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
                options["tolerance"] = 1e-3
                continue
            geom_size = get_layer_data_max_geometry_size(layer, **options)
            if geom_size > 2:
                print "geom size %s at %s" % (size, options)
                options["tolerance"] *= 10.0
                continue
            if "radius" not in options:
                options["radius"] = 1.0
                continue
            options["radius"] *= 10.0
            if options["radius"] > 4000000:
                break

        layer["data"] = get_layer_data(layer, **options)

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
