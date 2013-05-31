from django import forms

CHARACTER_ENCODINGS = [ ('utf-8' , 'UTF-8' ) ,  
                        ('ascii' , 'ASCI') , 
                        ('latin-1', 'Latin-1') ]

class ImportShapefileForm (forms.Form):

    import_file = forms.FileField (label="Select a Zipped Shapefile")
    character_encoding = forms.ChoiceField (choices = CHARACTER_ENCODINGS , initial="utf8" ) 

