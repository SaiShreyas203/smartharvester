from django import forms
from .models import Planting

class PlantingForm(forms.ModelForm):
    class Meta:
        model = Planting
        fields = ['crop_name', 'planting_date', 'batch_id', 'notes', 'image']
        widgets = {
            'planting_date': forms.DateInput(attrs={'type': 'date'}),
        }