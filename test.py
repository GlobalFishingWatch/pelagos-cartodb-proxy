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

def get_layer_fields(layer):
    return json.load(
        load_url(
            get_sql_url(
                layer,
                dict(
                    page=0,
                    sort_order="asc",
                    order_by="",
                    filter_column="",
                    filter_value="",
                    sql_source="null",
                    limit=0,
                    q=layer["options"]["sql"]
                    ))))["fields"]

def get_layer_data_sql(layer, bbox):
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
    """ % {
        "src": layer["options"]["sql"],
        "fields": ",".join([name for name in layer["fields"].keys() if name != "the_geom"]),
        "latmin": bbox.latmin,
        "latmax": bbox.latmax,
        "lonmin": bbox.lonmin,
        "lonmax": bbox.lonmax
    }


def get_layer_data_json_sql(layer, bbox):
    return """
        select
          ST_AsGeoJSON(the_geom, 8) the_geom,
          %(fields)s
        from
          (%(src)s) __wrapped__layer_data_json
    """ % {
        "src": get_layer_data_sql(layer, bbox),
        "fields": ",".join([name for name in layer["fields"].keys() if name != "the_geom"])
    }

def get_layer_data(layer, bbox):
    args = dict(
        page=0,
        sort_order="asc",
        order_by="",
        filter_column="",
        filter_value="",
        sql_source="null",
        q=get_layer_data_json_sql(layer, bbox)
        )

    layer_data = json.load(load_url(get_sql_url(layer, args)))

    for row in layer_data["rows"]:
        row["the_geom"] = json.loads(row["the_geom"])

    return layer_data['rows']

def get_layer_data_size(layer, bbox):
    query_sql = get_layer_data_sql(layer, bbox)
    size_sql = """
        select
          sum(ST_NPoints(the_geom)) as size
        from
          (%s) as __wrapped2
    """ % (query_sql,)

    args = dict(
        page=0,
        sort_order="asc",
        order_by="",
        filter_column="",
        filter_value="",
        sql_source="null",
        q=size_sql
        )

    res = json.load(load_url(get_sql_url(layer, args)))
    return res["rows"][0]["size"]

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
        print "NNNNNNNNNNNN", get_layer_data_size(layer, bbox)
        layer["data"] = get_layer_data(layer, bbox)

    data = reduce(operator.add, [layer["data"] for layer in layers], [])
    rows = []
    for row in data:
        row_data = {}
        for col_name, col in layer["fields"].iteritems():
            if col["type"] == "number":
                row_data[col_name] = row[col_name]
            elif col["type"] == "date":
                row_data[col_name] = (datetime.datetime.strptime(row[col_name], "%Y-%m-%dT%H:%M:%SZ") - datetime.datetime(1970, 1, 1)).total_seconds()

        geom = row["the_geom"]

        if geom['type'] == 'LineString':
            for coord in geom['coordinates']:
                out_row = dict(row_data)
                out_row.update({
                        "lat": coord[0],
                        "lon": coord[1],
                        })
                rows.append(out_row)

    # print(vectortile.Tile.fromdata(rows))

load_tile(urllib.quote("http://cartodb.localhost:4711/user/dev/api/v2/viz/2cf0043c-97ba-11e5-87b3-0242ac110002/viz.json"), None, "0,0,90,90")
