from django.contrib.gis import admin
from models import Shapefile, Feature, Attribute, AttributeValue

from models import BaseMap

admin.site.register (Shapefile, admin.ModelAdmin)
admin.site.register (Feature, admin.GeoModelAdmin)
admin.site.register (Attribute, admin.ModelAdmin)
admin.site.register (AttributeValue, admin.ModelAdmin)


# admin.site.register (BaseMap, admin.GeoModelAdmin)


