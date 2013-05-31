import tempfile
import os, os.path
import zipfile
import utils

from django.contrib.gis.geos.geometry import GEOSGeometry
import shutil, traceback
from osgeo import ogr , osr
from shapeEditor.models import Shapefile, Attribute, AttributeValue, Feature
from django.http import HttpResponse
from django.core.servers.basehttp import FileWrapper

# shapefile is an UploadedFile object representing the uploaded file.
# returns a string representing an error if one occurs

def importData (shapefile, characterEncoding ):

    fname = None

    # store a copy of the UploadedFile so it can be manipulated
    fd, fname = tempfile.mkstemp (suffix=".zip")
    os.close (fd)
    f = open (fname , "wb")
    for chunk in shapefile.chunks ():
        f.write (chunk)
    f.close ()

    # ----------

    if not zipfile.is_zipfile (fname):
      os.remove (fname)
      return "Not a valid zip archive %s " %(fname)

    # check that the shapefile zip has the required files
    zip = zipfile.ZipFile (fname)

    required_suffixes = [ ".shp" , ".shx" , ".dbf" , ".prj" ]
    hasSuffix = {}

    for suffix in required_suffixes:
      hasSuffix [suffix] = False

    for info in zip.infolist ():
      extn = os.path.splitext (info.filename) [1].lower ()
      if (extn in required_suffixes): 
        hasSuffix [extn] = True
 
    for suffix in required_suffixes:
      if not hasSuffix [suffix]:
        zip.close ()
        os.remove ( fname )
        return "Archive missing required "+suffix+"  file."

    # save the shapefile components (shp, dff etc) into
    # a temporary directory

    zip = zipfile.ZipFile (fname)
    shapefileName = None
    dirname = tempfile.mkdtemp ()
    for info in zip.infolist ():
        if info.filename.endswith (".shp"):
            shapefileName = info.filename
        dstFile = os.path.join ( dirname, info.filename )
        f = open (dstFile, "wb")
        f.write (zip.read ( info.filename ) )
        f.close ()
    zip.close ()

    # Use OGR to (try to) open up the Shapefile
    try:
        datasource= ogr.Open (os.path.join ( dirname ,  shapefileName ) ) 
        layer = datasource.GetLayer (0)
        shapeFileOK = True
    except:   
        traceback.print_exc()
        shapeFileOK = False
 
    if not  shapeFileOK:
        os.remove (fname)
        shutil.rmtree (dirname)
        return "Not a valid shapefile... couldn't open it with OGR"

    # Add the shapefile to the database
    srcSpatialRef = layer.GetSpatialRef ()

    geometryType = layer.GetLayerDefn ().GetGeomType ()
    geometryName = utils.ogrTypeToGeometryName (geometryType) 

    print "about to save shapefile. The details: " 
    print ".. srs_skt " + srcSpatialRef.ExportToWkt ()
    print ".. shapefileName: " + shapefileName


    # TODO. This will be truncated and should not be...
    srs_wkd = srcSpatialRef.ExportToWkt () [0:254]

    shapefile     = Shapefile ( filename = shapefileName , 
                                srs_wkd  = srs_wkd, 
                                geom_type= geometryName, 
                                encoding = characterEncoding)

    shapefile.save ()

    # Add the shapefile's attributes to the database

    attributes = []
    layerDef = layer.GetLayerDefn ()

    for counter in range ( layerDef.GetFieldCount () ):
        fieldDef = layerDef.GetFieldDefn ( counter ) 
        attr     = Attribute  (  shapefile = shapefile , 
                                 name      = fieldDef.GetName () , 
                                 type      = fieldDef.GetType () , # int code
                                 precision = fieldDef.GetPrecision () ,  
                                 width     = fieldDef.GetWidth () 
                              )

        attr.save ()
        attributes.append (attr)

    # Import the features
  
    dstSpatialRef = osr.SpatialReference () 
    dstSpatialRef.ImportFromEPSG ( 4326 ) 
    
    coordTransform  = osr.CoordinateTransformation ( srcSpatialRef , dstSpatialRef 	)    

    for count in range ( layer.GetFeatureCount () ):

        srcFeature   = layer.GetFeature ( count ) 
        srcGeometry  = srcFeature.GetGeometryRef () 
        srcGeometry.Transform ( coordTransform ) 

        # return a limited set of geometries .. 
        geometry = utils.wrapGEOSGeometry ( srcGeometry ) 

        # Geometry field will correspond with the field name in Feature class / table
        geometryField = utils.calcGeometryField (geometryName) \
                                                 # param is e.g. LineString / Point

        args = {}
        args[ 'shapefile'] = shapefile
        args[ geometryField] = geometry
        feature = Feature ( **args )       
          
        feature.save ()

        # save the attribute values
        for attr in attributes:

            # srcFeature (ogr.Layer.Feature) 
            # attr (shapeEditor.models.Attribute) 
            success, result = utils.getOGRFeatureAttribute (
                                  attr, srcFeature,
                                  characterEncoding ) 

            if not success:
                os.remove (fname)
                shutil.rmtree (dirname)
                shapefile.delete ()
                return result

            value = result
            attrValue = AttributeValue ( feature = feature, 
                                         attribute = attr , 
                                         value = value ) 
            attrValue.save ()

    os.remove (fname)
    shutil.rmtree (dirname)
    return None

def exportData (shapefile):

  dstDir  = tempfile.mkdtemp ()
  dstFile = str ( os.path.join (dstDir, shapefile.filename) ) 

  dstSpatialRef = osr.SpatialReference ()
  dstSpatialRef.ImportFromWkt ( shapefile.srs_wkd)

  driver     = ogr.GetDriverByName ( "ESRI Shapefile")
  datasource = driver.CreateDataSource ( dstFile )
  layer      = datasource.CreateLayer (  str ( shapefile.filename ), dstSpatialRef )   

  # find the spatial reference
  srcSpatialRef = osr.SpatialReference ()
  srcSpatialRef.ImportFromEPSG ( 4326 )
  coordTransform = osr.CoordinateTransformation ( srcSpatialRef , dstSpatialRef) 
  
  geomField = utils.calcGeometryField ( shapefile.geom_type ) 

  # Define layer attributes
  for attr in shapefile.attribute_set.all ():
    field = ogr.FieldDefn ( str ( attr.name ) , attr.type ) 
    field.SetWidth ( attr.width )
    field.SetPrecision ( attr.precision ) 
    layer.CreateField ( field ) 

  # Add all the (Single type) geometries for this layer 
  for feature in shapefile.feature_set.all ():

    # Geometry is a django construct inherited from GeometryField

    geometry = getattr ( feature , geomField ) 
    geometry = utils.unwrapGEOSGeometry  (geometry)

    dstGeometry = ogr.CreateGeometryFromWkt ( geometry.wkt ) 
    dstGeometry.Transform ( coordTransform ) 

    dstFeature = ogr.Feature ( layer.GetLayerDefn () ) 
    dstFeature.SetGeometry ( dstGeometry )

    # add in the feature's attributes
    for attrValue in feature.attributevalue_set.all ():
      utils.setOGRFeatureAttribute ( attrValue.attribute , 
                                     attrValue.value, 
                                     dstFeature, 
                                     shapefile.encoding)

    layer.CreateFeature ( dstFeature ) 
    dstFeature.Destroy ()

  datasource.Destroy ()
   
  # Compress the shapefile
  temp          = tempfile.TemporaryFile () 
  zipHandle      = zipfile.ZipFile ( temp, 'w' , zipfile.ZIP_DEFLATED ) 
  
  for fName in os.listdir ( dstDir ):
    zipHandle.write ( os.path.join ( dstDir , fName ) , fName ) 
  zipHandle.close ()

  # useful links to temp's directory
#  shapefileBase = os.path.splitext ( dstFile) [0]
  shapefileName = os.path.splitext ( shapefile.filename)[0]

  # Delete the temporary files
  shutil.rmtree ( dstDir ) 

  # Return the zip archive to the user
  f= FileWrapper ( temp ) 
  response = HttpResponse ( f , content_type="application\zip")
  response ['Content-Disposition'] = \
     "attachment; filename=" + shapefileName + ".zip"
  response ['Content-Length'] = temp.tell ()
  temp.seek (0)
  return response


