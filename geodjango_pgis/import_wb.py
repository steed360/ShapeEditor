from  shapeEditor.models import BaseMap
from django.contrib.gis.utils import LayerMapping

shapefile = "/home/john360/computing/geospatial_dev/geodjango_shapefile_app/TEST_DATA/TM_WORLD_BORDERS-0.3/TM_WORLD_BORDERS-0.3.shp"

BaseMap.objects.all().delete()
mapping = LayerMapping (BaseMap, 
                       shapefile, 
                       {'name':"NAME",'geometry':"MULTIPOLYGON"},
                       transform=False,
                       encoding="iso-8859-1")

mapping.save (strict=True, verbose=True)

print BaseMap.objects.count ()
print BaseMap.objects.all ()




