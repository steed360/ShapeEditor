
from django.http import HttpResponse
import traceback
from django.http import Http404
from shapeEditor.models import Shapefile
import math
import mapnik
import utils
import time
import geodjango1.settings as settings

MAX_ZOOM_LEVEL = 10
TILE_WIDTH    = 256
TILE_HEIGHT    = 256

def _unitsPerPixel ( zoomLevel ):
   # units are lat/long degrees
   # most panned out tile is 180 units/degrees
   # assume 256 pixels in any tile 

   # halve the degrees per pixel as many times as needed
   return ( 180.0 / float (TILE_WIDTH) ) / math.pow (2, zoomLevel )

def root (request):
#  return HttpResponse ("Tile Map Service")
  try:
    baseURL = request.build_absolute_uri ()
    xml = []
    xml.append ('<?xml version="1.0" encoding="utf-8"  ?>' ) 
    xml.append ('<Services>' ) 
    xml.append ('  <TileMapService '  + 
                '       title="ShapeEditor Tile Map Service" '     + 
                '       version="1.0" href="' + baseURL + '/1.0"  />' ) 
    xml.append  ('</Services>') 
    traceback.print_exc
    return HttpResponse ("\n".join (xml), mimetype="text/xml" ) 

  except:
    traceback.print_exec ()
    return HttpResponse (" ")

def service (request, version):
  try:
    if version != "1.0": 
       raise Http404   

    baseURL = request.build_absolute_uri ()
    xml = []
    xml.append ('<?xml version="1.0" encoding="utf-8"  ?>' ) 
    xml.append ('  <TileMapService '  + 
                '       version="1.0" services="' + baseURL + '" >' ) 
    xml.append ('     <Title>ShapeEditor Tile Map Service</Title>' )
    xml.append ('     <Abstract></Abstract> ' ) 
    xml.append ('     <TileMaps> ' ) 
    for shapefile in Shapefile.objects.all ():
         id = str ( shapefile.id )
         xml.append ( '       <TileMap title="' + shapefile.filename + '"'  )
         xml.append ( '          srs="EPSG:4326" ' ) 
         xml.append ( '          href="' + baseURL + '/' + id + '"/>'  )
    xml.append ('     </TileMaps> ' ) 
    xml.append ('  </TileMapService> ' )

    return HttpResponse ("\n".join (xml), mimetype="text/xml" ) 

  except:
    traceback.print_exec ()
    return HttpResponse (" ")

def tileMap (request, version, shapefile_id ) :
  try:

    if version != "1.0": 
       raise Http404   

    try:
      shapefile = Shapefile.objects.get ( id = shapefile_id )  
    except Shapefile.DoesNotExist:
        raise Http404 

    baseURL = request.build_absolute_uri ()
    xml = []
    xml.append ('<?xml version="1.0" encoding="utf-8"  ?>' ) 
    xml.append ('  <TileMap version="1.0" tilemapservice="'+ baseURL + '">' ) 
    xml.append ('    <Title>' + shapefile.filename + ' </Title>' )
    xml.append ('    <Abstract></Abstract>') 
    xml.append ('    <SRS>EPSG:4326</SRS>')
    xml.append ('    <BoundingBox minx="-180" miny="-90" maxx="180" maxy="90"/>')
    xml.append ('    <Origin x="-180" y="-90" /> ' )
    xml.append ('    <TileFormat width="' + str (TILE_WIDTH) + 
                      '" height="' + str (TILE_HEIGHT) + '" ' + 
                      'mime-type="image/png" extension="png"/>')
    xml.append ('    <TileSets profile="global-geodetic">' ) 

    for zoomLevel in range ( 0 , MAX_ZOOM_LEVEL + 1):
        unitsPerPixel = _unitsPerPixel (zoomLevel)
        xml.append ('       <TileSet href="' + baseURL + '/' + str ( zoomLevel ) + 
                                          '" units-per-pixel="' + str ( unitsPerPixel ) + '"' + 
                                          ' order="' + str (zoomLevel) + '" />' )

    xml.append ('    </TileSets> ')
    xml.append ('  </TileMap>')
    return HttpResponse ("\n".join (xml), mimetype="text/xml" ) 

  except:
    traceback.print_exc ()
    return HttpResponse (" ")


''' 
zoom 0=> covers entire world. Map is split into boxes
      => has two boxes 0,0 (left) and 1,0 (right) 

x,y start at bottom left

max (x, zoom) = 2^zoom (because at zoom 0 x in {0,1}
max (y, zoom0 = 2^zoom / 2   (at zoom 0, y in {0} 

max num of tiles = max (x,10) * max (y,10) =  1024  * 502

'''

def tile (request, version, shapefile_id, zoom, x, y):

  shapefile = None
  try:

    if version != "1.0":
      raise Http404
    try:
      shapefile = Shapefile.objects.get (id=shapefile_id)
    except Shapefile.DoesNotExist:
      raise Http404

    zoom = int (zoom)
    x    = int (x)
    y    = int (y)

    # min(x) = 0, max (x) =

    if zoom < 0 or zoom > MAX_ZOOM_LEVEL:
      raise Http404

    # for TILE_WIDTH/HEIGHT==256
    # at zoom = 0 extents will be 180 units/degrees

    xExtent  = _unitsPerPixel (zoom) * TILE_WIDTH
    yExtent  = _unitsPerPixel (zoom) * TILE_HEIGHT

    minLong  = xExtent * x - 180.0
    minLat   = yExtent * y -  90.0

    maxLong  = minLong + xExtent
    maxLat   = minLat  + xExtent    

    if ( minLong < -180 or maxLong > 180  or
        minLat < -90 or maxLat > 90):
         print "bound error raised"
         raise Http404

    dbFile        = "/home/john360/computing/geospatial_dev/geodjango_shapefile_app/DB/geodjango.db"
    extentStr = "%s,%s,%s,%s" %(minLong, minLat, maxLong, maxLat)

    map = mapnik.Map (TILE_WIDTH, TILE_HEIGHT, 
                      '+proj=longlat +datum=WGS84 +no_defs') 
 
    map.background = mapnik.Color ("#7391ad")


#    time.sleep (0.3)


    # Set up the base layer 
    datasource = \
             mapnik.SQLite(file=dbFile,
             table="shapeEditor_baseMap",
             key_field="id",
#             srid=4326,
             geometry_field="geometry",
             extent=extentStr,
             wkb_format="spatialite")

    baseLayer = mapnik.Layer ("baseLayer")      
    baseLayer.datasource = datasource
    baseLayer.styles.append ("baseLayerStyle")

    rule = mapnik.Rule ()

    rule.symbols.append ( 
      mapnik.PolygonSymbolizer (mapnik.Color ("#b5d19c") )
    )

    rule.symbols.append ( 
      mapnik.LineSymbolizer (mapnik.Color ("#404040"), 0.2 )
    )

    style = mapnik.Style ()
    style.rules.append ( rule ) 

    map.append_style ("baseLayerStyle", style)
    map.layers.append (baseLayer)

    # Define the feature layer

    geometryField = utils.calcGeometryField ( shapefile.geom_type)
    
    query = '( select ' + geometryField  +  \
            ' from "shapeEditor_feature" where ' + \
            'shapefile_id = ' + str(shapefile.id) + ' ) as geom'  

    dbSettings = settings.DATABASES['default']

    datasource = \
             mapnik.PostGIS(user=dbSettings['USER'],
                            password=dbSettings['PASSWORD'],
                            dbname=dbSettings['NAME'],
                            table=query,
                            srid=4326,
                            geometry_field=geometryField,
                            geometry_table='"shapeEditor_feature"')

    featureLayer = mapnik.Layer ("featureLayer")
    featureLayer.datasource = datasource
    featureLayer.styles.append ("featureLayerStyle")    

    rule = mapnik.Rule ()
	
    if shapefile.geom_type in ["Point", "MultiPoint"]:
      rule.symbols.append ( mapnik.LineSymbolizer (mapnik.Color ("#000000"), 0.5) )

    elif shapefile.geom_type in ["Polygon", "Multipolygon"]:

      rule.symbols.append ( mapnik.PolygonSymbolizer (mapnik.Color ("#b5d19c") ) )
      rule.symbols.append ( mapnik.LineSymbolizer (mapnik.Color ("#000000"), 1) )

    style = mapnik.Style () 
    style.rules.append (rule)

    map.append_style ("featureLayerStyle", style)
    map.layers.append (featureLayer)

    map.zoom_to_box (mapnik.Envelope (minLong, minLat, maxLong, maxLat ))
    image = mapnik.Image ( TILE_WIDTH, TILE_HEIGHT)

    mapnik.render (map, image)
    imageData = image.tostring ('png')

    return HttpResponse (imageData, mimetype="image/png")

  except:
    traceback.print_exc ()
    return HttpResponse (" ")

