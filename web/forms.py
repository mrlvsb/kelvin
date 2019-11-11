from django import forms

class UploadSolutionForm(forms.Form):
    solution = forms.FileField()