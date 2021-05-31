import sys
import os
import re

import httplib2
import json
import warnings
import types

import pandas as pd
import numpy as np

from collections import defaultdict
from googleapiclient.discovery import build


from .config import *
from .googoal import Google_service


if "google" in config:
    if "table_id" in config["google"]:
        table_id = os.path.expandvars(config["google"]["analytics_table"])
    else: 
        table_id = None
else:
    table_id = None


NEW_OAUTH2CLIENT = False
try:
    # See this change: https://github.com/google/oauth2client/issues/401
    from oauth2client.service_account import ServiceAccountCredentials

    NEW_OAUTH2CLIENT = True
except ImportError:
    try:
        from oauth2client.client import SignedJwtAssertionCredentials
    except ImportError:
        api_available = False


query_filters = []
query_filters.append(
    {
        "name": "traffic_goals",
        "dimensions": ["source", "medium"],
        "metrics": [
            "sessions",
            "goal1Starts",
            "goal1Completions",
            "goalStartsAll",
            "goalCompletionsAll",
            "goalValueAll",
        ],
        "sort": ["-goalCompletionsAll"],
        "docstr": "This query returns data for the first and all goals defined, sorted by total goal completions in descending order.",
    }
)
query_filters.append(
    {
        "name": "page_hits",
        "dimensions": ["pagePath"],
        "metrics": ["pageviews"],
        "sort": ["-pageviews"],
        "filters": "ga:pagePath!@index.html;ga:pagePath!@faq.html;ga:pagePath!@spec.html",
        "docstr": "This query retuns the number of page hits",
    }
)
for i in range(4):
    n = str(i + 1)
    query_filters.append(
        {
            "name": "goal" + n + "_completion",
            "dimensions": ["goalCompletionLocation"],
            "metrics": ["goal" + n + "Completions"],
            "sort": ["-goal" + n + "Completions"],
            "filters": None,
            "docstr": "This query retuns the number of goal "
            + n
            + "1 completions.",
        }
    )
query_filters.append(
    {
        "name": "mobile_traffic",
        "dimensions": ["mobileDeviceInfo"],
        "metrics": ["sessions", "pageviews", "sessionDuration"],
        "segment": "gaid::-14",
        "sort": ["-pageviews"],
        "docstr": """This query returns some information about sessions which occurred from mobile devices. Note that "Mobile Traffic" is defined using the default segment ID -14.""",
    }
)
query_filters.append(
    {
        "name": "referring_sites",
        "dimensions": ["source"],
        "metrics": ["pageviews", "sessionDuration", "exits"],
        "filters": "ga:medium==referral",
        "sort": ["-pageviews"],
    }
)


def gqf_(
    name=None,
    docstr=None,
    dimensions=None,
    metrics=None,
    sort=None,
    filters=None,
    segment=None,
):
    """Generate query functions for different dimensions and metrics"""

    def fun(self):
        def prefix(string):
            if string[0] == "-":
                return "-ga:" + string[1:]
            else:
                return "ga:" + string

        def preplist(str_list):
            if str_list is None:
                return None
            if isinstance(str_list, str):
                return str_list
            new_list = []
            for v in str_list:
                new_list.append(prefix(v))
            return ",".join(new_list)

        self._dimensions = preplist(dimensions)
        self._metrics = preplist(metrics)
        self._sort = preplist(sort)
        self._filters = preplist(filters)
        self._segment = preplist(segment)
        self.raw_query()
        result = self._query.execute()

        columns = []
        for c in result["columnHeaders"]:
            name = re.sub("(.)([A-Z][a-z]+?)", r"\1 \2", c["name"][3:])
            name = name[0].upper() + name[1:]
            columns.append(name)
        df = pd.DataFrame(result["rows"], columns=columns)

        for c, col in zip(result["columnHeaders"], columns):
            if c["dataType"] == "INTEGER":
                df[[col]] = df[[col]].astype(int)
        return df

    if name is not None:
        fun.__name__ = name
    if docstr is not None:
        fun.__doc__ = docstr
    return fun

class Analytics(Google_service):
    """
    Class for accessing google analytics and analyzing data.
    """

    def __init__(
        self, scope=None, credentials=None, http=None, service=None, table_id=None
    ):
        if scope is None:
            scope = ["https://www.googleapis.com/auth/analytics.readonly"]
        Google_service.__init__(
            self, scope=scope, credentials=credentials, http=http, service=service
        )
        if service is None:
            self.service = build("analytics", "v3", http=self.http)

        if table_id is None:
            # Table_id is found on Admin:View under google analytics page
            table_id = os.path.expandvars(config.get("google", "analytics_table"))
        self._table_id = table_id
        self._start_date = "30daysAgo"  # 2017-07-01'
        self._end_date = "yesterday"  # 2017-08-01'

        self._start_index = 1
        self._max_results = 100

        self._dimensions = "ga:pagePath"
        self._metrics = "ga:pageviews"

        self._filters = None
        self._segment = None
        self._sort = None

        # Auto create the query functions
        for query in query_filters:
            self.__dict__[query["name"]] = types.MethodType(gqf_(**query), self)

    def set_start_date(self, date):
        """Set the start date for queries"""
        self._start_date = date

    def set_end_date(self, date):
        """Set the end date for queries"""
        self._end_date = date

    def set_max_results(self, max_results):
        """Set maximum results to return for queries"""
        self._max_results = max_results

    def set_start_index(self, start_index):
        """Set start index of results to return for queries"""
        self._start_index = start_index

    def dataframe_query(self):
        self.raw_query().execute()

    def raw_query(self):
        """Builds a query object to retrieve data from the Core Reporting API."""
        # Use this to explore: https://ga-dev-tools.appspot.com/query-explorer/
        # And this as reference: https://developers.google.com/analytics/devguides/reporting/core/v3/reference
        self._query = (
            self.service.data()
            .ga()
            .get(
                ids=self._table_id,
                start_date=self._start_date,
                end_date=self._end_date,
                metrics=self._metrics,
                dimensions=self._dimensions,
                sort=self._sort,
                filters=self._filters,
                start_index=str(self._start_index),
                max_results=str(self._max_results),
                segment=self._segment,
            )
        )


