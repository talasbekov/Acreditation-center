from django import forms
from .models import QrIin

class QrIinForm(forms.ModelForm):
    class Meta:
        model = QrIin
        fields = ['iin']
        widgets = {
            'iin': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите ИИН',
                'maxlength': '12'
            })
        }
