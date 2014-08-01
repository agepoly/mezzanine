from __future__ import unicode_literals

from django.conf.urls import patterns, url
from django.conf import settings

from mezzanine.pages import page_processors

page_processors.autodiscover()


# Page patterns.
urlpatterns = patterns("mezzanine.forms.views",
    url("^start_payment/(?P<pk>[0-9]+)$", "start_payment"),
    url("^ipn$", "ipn"),
    url("^ok$", "result_ok"),
    url("^err$", "result_err"),
)
