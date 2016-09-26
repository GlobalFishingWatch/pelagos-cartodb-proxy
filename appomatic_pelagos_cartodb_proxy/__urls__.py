from django.conf.urls import *
from django.conf import settings

urlpatterns = patterns('',
    url(r'^tiles/(?P<tileset>.*)/header$', 'appomatic_pelagos_cartodb_proxy.views.header'),
    url(r'^tiles/(?P<tileset>.*)/(?P<time>[^/]*);(?P<bbox>[^/]*)$', 'appomatic_pelagos_cartodb_proxy.views.tile'),
    url(r'^tiles/(?P<tileset>.*)/(?P<bbox>[^/]*)$', 'appomatic_pelagos_cartodb_proxy.views.tile'),
)
