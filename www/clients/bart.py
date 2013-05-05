#
#
#

from collections import OrderedDict
from www.info.models import Direction, Prediction, Route, Stop, \
    route_types, stop_types
from xmltodict import parse
from .utils import RateLimitedSession
import requests


class Bart:
    url = 'http://api.bart.gov/api/';
    params = {'key': 'MW9S-E7SL-26DU-VV8V'};

    def __init__(self, agency):
        self.agency = agency

        self.session = RateLimitedSession()

        self._cached_all_stops = None

    def routes(self):
        agency = self.agency

        url = '{0}{1}'.format(self.url, 'route.aspx')
        params = dict(self.params)
        params['cmd'] = 'routes'

        resp = self.session.get(url, params=params)

        # preserve BART's order
        routes = OrderedDict()
        for route in parse(resp.content)['root']['routes']['route']:
            color = route['color']
            if color not in routes:
                id = Route.create_id(agency.id, route['number'])
                routes[color] = Route(id=id, agency=agency, name=route['name'],
                                      sign=route['abbr'], type=route_types[1],
                                      color=route['color'],
                                      order=len(routes))
            else:
                routes[color].id = '{0}-{1}'.format(routes[color].id,
                                                    route['number'])

        return list(routes.values())

    def _all_stops(self):
        if self._cached_all_stops:
            return self._cached_all_stops

        url = '{0}{1}'.format(Bart.url, 'stn.aspx')
        params = dict(Bart.params)
        params['cmd'] = 'stns'

        resp = self.session.get(url, params=params)

        data = parse(resp.content)
        stops = {}
        for station in data['root']['stations']['station']:
            # don't care about having "real" ids here
            stop = Stop(agency=self.agency, id=station['abbr'],
                        name=station['name'], lat=station['gtfs_latitude'],
                        lon=station['gtfs_longitude'], type=stop_types[1])
            stops[stop.id] = stop

        self._cached_all_stops = stops

        return stops

    def _route_info(self, route, number):
        url = '{0}{1}'.format(Bart.url, 'route.aspx')
        params = dict(Bart.params)
        params['cmd'] = 'routeinfo'
        params['route'] = number

        resp = self.session.get(url, params=params)

        data = parse(resp.content)['root']['routes']['route']
        # list of stations this route passes
        abbrs = data['config']['station']
        # will block if we don't already have an answer
        all_stops = self._all_stops()
        stop_ids = []
        stops = {}
        # origin
        origin = abbrs.pop(0)
        for abbr in abbrs:
            # copy over the relevant stations
            stop = all_stops[abbr]
            stop = Stop(agency=route.agency,
                        id=Stop.create_id(route.agency.id,
                                          '{0}-{1}'.format(abbr, origin)),
                        name=stop.name, lat=stop.lat, lon=stop.lon,
                        type=stop.type)
            stop_ids.append(stop.id)
            stops[stop.id] = stop
        direction = Direction(route=route,
                              id=Direction.create_id(route.id, number),
                              name=data['name'])
        direction.stop_ids = stop_ids

        return (direction, stops)

    def stops(self, route):
        a, b = route.get_id().split('-')
        direction_a, stops = self._route_info(route, a)
        direction_b, stps = self._route_info(route, b)
        stops.update(stps)

        return ([direction_a, direction_b], stops)

    def _stop_predictions(self, stop):
        return []

        # TODO: this needs to be able to link predictions to directions
        abbr = stop.get_id().split('-')[0]

        url = '{0}{1}'.format(self.url, 'etd.aspx')
        params = dict(self.params)
        params['cmd'] = 'etd'
        # the station we're interested in
        params['orig'] = abbr
        resp = requests.get(url, params=params)

        predictions = []
        for direction in parse(resp.content)['root']['station']['etd']:
            for prediction in direction['estimate']:
                try:
                    away = int(prediction['minutes']) * 60
                except ValueError:
                    continue
                did = 'sf:bart:'
                predictions.append(Prediction(stop=stop, away=away,
                                              unit='seconds',
                                              direction_id=did))

        return predictions

    def _route_predictions(self, stop, route):
        abbr, dest = stop.get_id().split('-')

        url = '{0}{1}'.format(self.url, 'etd.aspx')
        params = dict(self.params)
        params['cmd'] = 'etd'
        params['orig'] = abbr
        resp = requests.get(url, params=params)

        for direction in parse(resp.content)['root']['station']['etd']:
            if not dest or direction['abbreviation'] == dest:
                predictions = []
                for prediction in direction['estimate']:
                    try:
                        away = int(prediction['minutes']) * 60
                    except ValueError:
                        continue
                    predictions.append(Prediction(stop=stop, away=away,
                                                  unit='seconds'))
                return predictions

        return []

    def predictions(self, stop, route=None):
        if route:
            return self._route_predictions(stop, route)
        return self._stop_predictions(stop)
