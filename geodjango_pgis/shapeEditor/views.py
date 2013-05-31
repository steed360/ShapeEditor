# Create your views here.

from django.http import HttpResponse
from django.shortcuts import render_to_response
from shapeEditor.models import Shapefile, Feature
import traceback
import django.contrib.gis.geos
import utils

from django.http import HttpResponseRedirect
from shapeEditor.forms import ImportShapefileForm

from shapeEditor import shapeFileIO

def listShapefiles (request):
#    return HttpResponse ("In listShapefiles")
    shapefiles = Shapefile.objects.all ().order_by ("filename")
    return render_to_response ("listShapefiles.html", 
                               {'shapefiles': shapefiles } )

def importShapefile (request):

    # The first time the view is called
    if (request.method == "GET"):
        form = ImportShapefileForm ()
  
        return render_to_response ("importShapefile.html", {'form': form, 
                                                            'errMsg': None}  ) 

    # The second time - should be some user data

    if (request.method == "POST"): 
        form = ImportShapefileForm (request.POST, request.FILES)
        errMsg = None

        if (form.is_valid () ):
            shapefile = request.FILES [('import_file')  ]
            encoding = request.POST ['character_encoding']

            errMsg = shapeFileIO.importData (shapefile, encoding ) 

            if (errMsg == None):
                # more to come
                return HttpResponseRedirect ("/shape-editor")

        return render_to_response  ( 'importShapefile.html', {'form':form , 
                                                          'errMsg':errMsg } )
        
def exportShapefile ( request, shapefile_id ):
    try:
        shapefile = Shapefile.objects.get ( id=shapefile_id)
    except Shapefile.DoesNotExist:
        raise Http404
    return shapeFileIO.exportData (shapefile)

def editShapefile (request, shapefile_id) : 

    shapefile = None
    try:
        shapefile = Shapefile.objects.get (id=shapefile_id )
    except:
        raise Http404

    tmsURL         = "http://" + request.get_host () + "/shape-editor/tms"
    findFeatureURL = "http://" + request.get_host () + "/shape-editor/findFeature" 
    addFeatureURL  = "http://" + request.get_host () + "/shape-editor/editFeature/" + str(shapefile_id) 

    return render_to_response ("selectFeature.html", 
                               {  'shapefile'     : shapefile,
                                  'findFeatureURL': findFeatureURL, 
                                  'addFeatureURL' : addFeatureURL,
                                  'tmsURL'        : tmsURL 
                               } )

def findFeature (request) : 

    try: 
       # TODO: fix this so that it works as in the book
       # may need to switch to PostGIS

        shapefile_id = int ( request.GET ['shapefile_id'] )
        latitude   = float ( request.GET ['latitude'] ) 
        longitude  = float ( request.GET ['longitude'] ) 

        shapefile = Shapefile.objects.get (id = shapefile_id ) 

        pt = django.contrib.gis.geos.Point (longitude, latitude)
        radius = utils.calcSearchRadius ( latitude, longitude , 100) 

        # Create a circle polygon. TODO check what this is really doing.
        circleGeom = pt.buffer ( radius )

        if shapefile.geom_type == "Point":
            query = Feature.objects.filter ( geom_point__within  =  circleGeom)

        elif shapefile.geom_type in ["LineString", "MultiLineString"]:
            query = Feature.objects.filter ( geom_multilinestring__dwithin =( pt, radius))
            print query



        elif shapefile.geom_type in ["Polygon", "MultiPolygon"]:
            print 'its here'
            #query = Feature.objects.filter ( geom_multipolygon__contains = pt  )
            query = Feature.objects.filter ( geom_multipolygon__dwithin =( pt, radius))

        elif shapefile.geom_type == "Multipoint":
            query = Feature.objects.filter ( geom_multipoint__within = circleGeom)

        elif shapefile.geom_type == "GeometryCollection":
            query = Feature.objects.filter ( geom_geometryCollection__contains = circleGeom)

        else:
            print "Unsupported GEometry: " + shapefile.geom_type
            return HttpResponse ("")

        if query.count () != 1:
            print 'oh dear: ' + str (query.count () ) 
            return HttpResponse ("")
   
        feature = query.all () [0] 
        return HttpResponse ("/shape-editor/editFeature/" + str (shapefile_id) + "/" + str (feature.id )  )
 
    except:
        traceback.print_exc()
        return HttpResponse("")


def editFeature (request, shapefile_id, feature_id=None) :

    if request.method == "POST" and "delete" in request.POST:
        return HttpResponseRedirect ("/shape-editor/deleteFeature/" + shapefile_id + "/" + feature_id)

    try:
        shapefile = Shapefile.objects.get (id = shapefile_id)
    except:
        raise Http404

    if feature_id == None:
        feature = Feature (shapefile=shapefile)
    else:
        try:
            feature = Feature.objects.get (id = feature_id)
        except Feature.DoesNotExist:
            raise Http404

    attributes = []
    for attrValue in feature.attributevalue_set.all ():
        attributes.append ( [attrValue.attribute.name, attrValue.value]  ) 
    attributes.sort ()

    geometryField = utils.calcGeometryField ( shapefile.geom_type ) 
    formType      = utils.getMapForm (shapefile)

    if request.method == "GET":
       wkt   =  getattr ( feature, geometryField)
       form  = formType ( { 'geometry' : wkt }  ) 

       return render_to_response ( "editFeature.html", { 'shapefile' : shapefile, 
                                                         'form'      : form , 
                                                         'attributes': attributes   } )
    elif request.method == "POST":

        form = formType (request.POST)
        try:
            if form.is_valid():
                wkt = form.cleaned_data ['geometry']
                setattr (feature, geometryField, wkt)
                feature.save () 
                return HttpResponseRedirect ("/shape-editor/edit/" + str (shapefile.id))

        except ValueError:
            pass
        return render_to_response ("editFeature.html",
                                   { 'shapefile' : shapefile, 
                                     'form'      : form, 
                                     'attributes': attributes
                                   } )

def deleteFeature (request, shapefile_id, feature_id):
    try:
        feature = Feature.objects.get ( id = feature_id )
    except Feature.DoesNotExist:
        raise Http404

    if  request.method == "POST":
        if request.POST['confirm'] == "1":
            feature.delete ()
        return HttpResponseRedirect ("/shape-editor/edit/" + shapefile_id   )
    return render_to_response ("deleteFeature.html")


def deleteShapefile (request, shapefile_id):
    try:
        shapefile = Shapefile.objects.get ( id = shapefile_id)
    except Shapefile.DoesNotExist:
        raise Http404
    if request.method == "GET":
        return render_to_response ("deleteShapefile.html", 
                                   {'shapefile': shapefile}
                                  )
    elif request.method == "POST": 
        if request.POST["confirm"] == "1":
            shapefile.delete ()
        return HttpResponseRedirect ("/shape-editor")



