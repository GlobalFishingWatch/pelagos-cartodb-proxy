import json
import urllib
import urllib2
import operator
import re
import google.appengine.api.urlfetch

google.appengine.api.urlfetch.set_default_fetch_deadline(60)

def load_url(*arg, **kw):
    try:
        return urllib2.urlopen(*arg, **kw)
    except urllib2.HTTPError as e:
        e.msg = e.read()
        raise e

def get_sql_url(layer):
    sql_url = layer["options"]["sql_api_template"].replace("{user}", layer["options"]["user_name"]) + layer["options"]["sql_api_endpoint"]
    return sql_url

def get_sql_args(args):
    return "&".join(["%s=%s" % (name, urllib.quote(unicode(value)))
                     for name, value in args.iteritems()])

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
                get_sql_url(layer),
                data=get_sql_args(args)))
    except urllib2.HTTPError as e:
        if "q" in kw:
            e.msg = "%s while executing %s" % (e.msg, kw["q"])
        raise e
