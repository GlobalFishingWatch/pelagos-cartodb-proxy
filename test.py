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

def load_tile(tileset = None, time = None, bbox = None):
    tileset = urllib.unquote(tileset)
    bbox = vectortile.Bbox.fromstring(bbox)

    tileset_spec = json.load(load_url(tileset))

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

    for layer in layers:
        sql_url = layer["options"]["sql_api_template"].replace("{user}", layer["options"]["user_name"]) + layer["options"]["sql_api_endpoint"]

        query = """
            select
              ST_AsGeoJSON(ST_Intersection(ST_MakeEnvelope(%(lonmin)s, %(latmin)s, %(lonmax)s, %(latmax)s, 4326), the_geom), 8) _the_geom,
              *
            from
              (%(src)s) __wrapped
            where
              ST_Contains(ST_MakeEnvelope(%(lonmin)s, %(latmin)s, %(lonmax)s, %(latmax)s, 4326), the_geom)
            order by
              cartodb_id asc
        """ % {
            "src": layer["options"]["sql"],
            "latmin": bbox.latmin,
            "latmax": bbox.latmax,
            "lonmin": bbox.lonmin,
            "lonmax": bbox.lonmax
        }

        args = dict(
            page=0,
            sort_order="asc",
            order_by="",
            filter_column="",
            filter_value="",
            sql_source="null",
            q=query
            )

        query_url = "%s?%s" % (sql_url, "&".join(["%s=%s" % (name, urllib.quote(value)) for name, value in args.iteritems()]))

        layer_data = json.load(load_url(query_url))
        for row in layer_data["rows"]:
            row["the_geom"] = json.loads(row["_the_geom"])

        layer["data"] = layer_data["rows"]
        layer["fields"] = layer_data["fields"]

    data = reduce(operator.add, [layer["data"] for layer in layers], [])
    rows = []
    for row in data:
        row_data = {}
        for col_name, col in layer["fields"].iteritems():
            if col["type"] == "number":
                row_data[col_name] = row[col_name]
            elif col["type"] == "date":
                row_data[col_name] = (datetime.datetime.strptime(row[col_name], "%Y-%m-%dT%H:%M:%SZ") - datetime.datetime(1970, 1, 1)).total_seconds()

        geom = json.loads(row["_the_geom"])

        if geom['type'] == 'LineString':
            for coord in geom['coordinates']:
                out_row = dict(row_data)
                out_row.update({
                        "lat": coord[0],
                        "lon": coord[1],
                        })
                rows.append(out_row)

    print(vectortile.Tile.fromdata(rows))

load_tile(urllib.quote("http://cartodb.localhost:4711/user/dev/api/v2/viz/2cf0043c-97ba-11e5-87b3-0242ac110002/viz.json"), None, "0,0,90,90")
