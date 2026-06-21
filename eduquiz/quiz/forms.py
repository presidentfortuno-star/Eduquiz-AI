from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Document, Quiz


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'placeholder': 'Titre du cours, par exemple HTML',
                    'class': 'input-field',
                }
            ),
            'file': forms.ClearableFileInput(
                attrs={'accept': '.pdf', 'class': 'input-field'}
            ),
        }


class QuizCreateForm(forms.ModelForm):
    question_count = forms.ChoiceField(
        choices=[('10', '10 questions'), ('20', '20 questions'), ('50', '50 questions')],
        initial='10',
        label='Nombre de questions',
    )
    level = forms.ChoiceField(
        choices=Quiz._meta.get_field('level').choices,
        initial='easy',
        label='Niveau',
    )

    class Meta:
        model = Quiz
        fields = ['question_count', 'level']