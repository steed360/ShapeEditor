
from osgeo import ogr
from django.contrib.gis.geos.collections \
     import MultiPolygon, MultiLineString

from django.contrib.gis.geos import geometry as modGEOSGeometry
import pyproj

from django import forms
from django.contrib.gis import forms
import django.contrib.gis.admin as gisAdmin

from models import Feature

def ogrTypeToGeometryName (ogrType):
  return {
    ogr.wkbUnknown            : 'Unknown', 
    ogr.wkbPoint              : 'Point', 
    ogr.wkbLineString         : 'LineString', 
    ogr.wkbPolygon            : 'Polygon', 
    ogr.wkbMultiPoint         : 'MultiPoint', 
    ogr.wkbMultiLineString    : 'MultiLineString', 
    ogr.wkbMultiPolygon       : 'MultiPolygon', 
    ogr.wkbGeometryCollection : 'GeometryCollection', 
    ogr.wkbNone               : 'None', 
    ogr.wkbLinearRing         : 'LinearRing', 
  }.get ( ogrType )

# geometry is in 'Well Known Text' format
def wrapGEOSGeometry ( geometry ):
  print geometry.GetGeometryName ()
  if  geometry.GetGeometryName () == "POLYGON":
#    return MultiPolygon (geometry.ExportToWkt () )
    return MultiPolygon ( modGEOSGeometry.GEOSGeometry (geometry.ExportToWkt () ) )
  if  geometry.GetGeometryName () == "LINESTRING":
    print "returning linestring"
    return MultiLineString (modGEOSGeometry.GEOSGeometry (geometry.ExportToWkt () ))
#    return MultiLineString (geometry.ExportToWkt () )
  return modGEOSGeometry.GEOSGeometry (geometry.ExportToWkt () )



# geometryType is a string
def calcGeometryField ( geometryType ):
  if geometryType == "Polygon":
    return "geom_multipolygon"
  elif geometryType == "LineString":
    return "geom_multilinestring"
  else:
    return "geom_" + geometryType.lower ()

# attr    - models.Attribute
# feature - ogr.Layer.Feature
# encoding- user input from drop down list = utf8


def removeNonAscii(s): return "".join(i for i in s if ord(i)<128)

def getOGRFeatureAttribute (  attr, feature, encoding ):
  attrName = str ( attr.name )

  if not feature.IsFieldSet ( attrName ):
    return (True, None)
  needsEncoding = False

  if attr.type   == ogr.OFTInteger:  # int code
    value = str (feature.GetFieldAsInteger (attrName))

  elif attr.type == ogr.OFTIntegerList:
    value =  repr ( feature.GetFieldAsIntegerList ( attrName ) ) 

  elif attr.type == ogr.OFTReal:
    value = feature.GetFieldAsDouble ( attrName ) 
    value = "%*.*f" %(attr.width, attr.precision, value)

  elif attr.type == ogr.OFTRealList: 
    values = feature.GetFieldAsDoubleList ( attrName ) 
    sValue = [] 
    for value in values:
      sValues.append ( "%*.*f" %(attr.width, attr.precision, value) )
    values = repr (sValues)  

  elif attr.type == ogr.OFTString:
    value = feature.GetFieldAsString (attrName)
    value = removeNonAscii (value)
    needsEncoding = True

  elif attr.type == ogr.OFTStringList:
    value = repr ( feature.GetFieldAsStringList ( attrName))
    needsEncoding = True
 
  elif attr.type == ogr.OFTDate: 
    parts=feature.GetFieldAsDateTime ( attrName ) 
    year, month, day, hour,minute,second,tzone = parts
    value="%d,%d,%d,%d,%d,%d,%d" % (year,month,day,hour,minute,second,tzone)

  else:
    return (False, "Unsupported attribute type: " + str (attr.type ))

  if needsEncoding:
    try: 
      value = value.decode ( encoding)
    except UnicodeDecodeError:
      return ( False, "Unable to decode values in " + 
               repr (  attrName ) + 
               "&nbsp Are you sure you're using the right character encoding? "
              )
  return (True, value)

def unwrapGEOSGeometry (geometry):
  if geometry.geom_type in ["Multipolygon", "MultiLineString"]:
    if len ( geometry ) == 1:
      geometry = geometry [0]
  return geometry


# attr: Models.Attribute , value: STRING, feature: OGR shapefile feature, 
# encoding was stored by user on creation

def setOGRFeatureAttribute (attr, value , feature, encoding):

  attrName = str ( attr.name ) 

  if value == None:
    feature.UnsetField ( attrName ) 
    return

  if attr.type == ogr.OFTInteger:
    feature.SetField ( attrName , int (value) ) 
  
  elif attr.type == ogr.OFTIntegerList:
    integers = eval ( value ) 
    feature.SetFieldIntegerList ( attrName, integers ) 

  elif attr.type == ogr.OFTReal:
    feature.SetField ( attrName, float ( value ) ) 

  elif attr.type == ogr.OFTRealList:
    floats = []
    for s in eval (value):
      floats.append ( eval ( s ) ) 
    feature.SetFieldDoubleList ( attrName , floats ) 

  elif attr.type == ogr.OFTString:
    feature.SetField ( attrName , value.encode ( encoding ) )
  
  elif attr.type == ogr.OFTStringList:
    strings = []
    for s in eval (value):
      strings.append ( s.encode ( encoding ) ) 
    feature.SetFieldStringList ( attrName, strings) 

  elif attr.type == ogr.OFTDate:
    parts  = value.split (",")
    year   = int ( parts [0] )   
    month  = int ( parts [1] )   
    day    = int ( parts [2] )   
    tzone  = int ( parts [3] )   

    feature.SetField ( attrName, year, month, day , 0,0,0, tzone) 

  elif attr.type == ogr.OFTTime:
    parts  = value.split (",")
    hour   = int ( parts [0] )   
    minute  = int ( parts [1] )   
    day    = int ( parts [2] )   
    second  = int ( parts [3] )   

    feature.SetField ( attrName , 0,0,0, hour, minute, second, tzone) 


  elif attr.type == ogr.OFTDateTime:
    parts  = value.split (",")
    year    = int ( parts [0] )   
    month   = int ( parts [1] )   
    day     = int ( parts [2] )   
    hour    = int ( parts [3] )   
    minute  = int ( parts [4] )   
    day     = int ( parts [5] )   
    second  = int ( parts [6] )   

    feature.SetField (  attrName, year, month, day , hour, minute, second, tzone)
  

def calcSearchRadius ( latitude, longitude, distance):
    geod = pyproj.Geod (ellps="WGS84")
    x,y,angle = geod.fwd ( longitude, latitude, 0 , distance) 

    radius = y-latitude

    x,y,angle = geod.fwd ( longitude, latitude, 180, distance)
    radius = max ( radius, x-longitude)

    x,y,angle = geod.fwd ( longitude, latitude, 180, distance)
    radius = max ( radius, latitude-y)

    x,y,angle = geod.fwd ( longitude, latitude, 270, distance)
    radius = max ( radius, longitude-y)

    print "returning " + str ( radius)
    return radius

def getMapForm (shapefile):
    geometryField   = calcGeometryField ( shapefile.geom_type)
    adminInstance   = gisAdmin.GeoModelAdmin ( Feature, gisAdmin.site ) 
    field           = Feature._meta.get_field ( geometryField ) 
    widgetType      = adminInstance.get_map_widget (field)

    class MapForm (forms.Form):
      geometry = forms.CharField ( widget = widgetType (), label = "")

    return MapForm

