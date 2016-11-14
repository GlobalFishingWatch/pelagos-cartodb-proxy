import cartosql
import json

def load_layer_fields(layer):
    layer['fields'] = cartosql.exec_sql(
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

def load_layer_geometry_types(layer):
    layer["options"]["geometry_types"] = [
      row["type"] for row in
      cartosql.exec_sql(
            layer,
            q="""
              select
                GeometryType(the_geom) as type
              from
                (%(src)s) __wrapped__layer_geometry_type
              group by type
            """ % {"src": layer["options"]["sql"]})['rows']]
    
def annotate_layer(layer):
    """Load all layer metadata and annotate a layer with default
    values for missing optional columns."""

    load_layer_fields(layer)
    load_layer_geometry_types(layer)
    is_point_layer = layer["options"]["geometry_types"] == ["POINT"]
    
    original_fields = layer['fields'].keys()
    added_fields = []

    if "series_group" not in layer['fields']:
        if is_point_layer:
            added_fields.append("1 as series_group")
        else:
            added_fields.append("row_number() over () as series_group")
        layer['fields']["series_group"] = {"type": "number"}
    if "series" not in layer['fields']:
        if is_point_layer:
            added_fields.append("1 as series")
        else:
            added_fields.append("row_number() over () as series")
        layer['fields']["series"] = {"type": "number"}
    if "sigma" not in layer['fields']:
        added_fields.append("0.0 as sigma")
        layer['fields']["sigma"] = {"type": "number"}
    if "weight" not in layer['fields']:
        added_fields.append("1.0 as weight")
        layer['fields']["weight"] = {"type": "number"}

    if added_fields:
        layer["options"]["sql"] = """
          select
            %(fields)s
          from
            (%(src)s) as __wrapped__annotate_layer
        """ % {"src": layer["options"]["sql"],
               "fields": ",".join(original_fields + added_fields)
               }

def load_tileset(tileset):
    tileset_spec = json.load(cartosql.load_url(tileset))

    layers = find_layers(tileset_spec)

    for layer in layers:
        annotate_layer(layer)

    return tileset_spec, layers
