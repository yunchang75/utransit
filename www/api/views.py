#
#
#

from django.http import Http404
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.renderers import BrowsableAPIRenderer
from www.api.clients import get_provider
from www.api.models import agency_lists, agencies, region_list, regions
from www.api.renderers import JSONRenderer


class BaseView(APIView):
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)

    def metadata(self, request):
        data = super(BaseView, self).metadata(request)
        # remove parses since we're read-only
        del data['parses']
        return data

    def get(self, request, *args, **kwargs):
        return Response(self.get_data(request, *args, **kwargs))


class ApiRoot(BaseView):
    '''
    The entry endpoint of our API
    '''

    def get(self, request, *args, **kwargs):
        return Response({
            'regions': reverse('regions-list', request=request),
        })


class RegionList(BaseView):
    '''
    A list of Regions
    '''


    def get_data(self, request):
        return [region.data for region in region_list]


class RegionDetail(BaseView):
    '''
    A Region's Details
    '''

    def get_data(self, request, id):
        if id not in regions:
            raise Http404()
        data = regions[id].data
        data['agencies'] = [agency.data for agency in agency_lists[id]]
        return data


class AgencyDetail(BaseView):
    '''
    An Agency's Details
    '''

    def get_data(self, request, region, id):
        if id not in agencies:
            raise Http404()
        agency = agencies[id]
        future = get_provider(agency.provider).routes(id)
        data = agency.data
        data['routes'] = [route.data for route in future.result().routes]
        return data