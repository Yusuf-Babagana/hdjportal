from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import FormActions
from .models import *

class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone = forms.CharField(max_length=17, required=True)
    referral_code = forms.CharField(max_length=10, required=False, 
                                  help_text="Optional: Enter referral code to skip payment")

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'password1', 'password2', 'referral_code')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h4 class="mb-4"><i class="fas fa-user-plus"></i> Student Registration</h4>'),
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-3'),
                Column('last_name', css_class='form-group col-md-6 mb-3'),
                css_class='form-row'
            ),
            Row(
                Column('username', css_class='form-group col-md-6 mb-3'),
                Column('email', css_class='form-group col-md-6 mb-3'),
                css_class='form-row'
            ),
            Field('phone', css_class='form-control mb-3'),
            Field('referral_code', css_class='form-control mb-3'),
            Row(
                Column('password1', css_class='form-group col-md-6 mb-3'),
                Column('password2', css_class='form-group col-md-6 mb-3'),
                css_class='form-row'
            ),
            FormActions(
                Submit('submit', 'Register', css_class='btn btn-primary btn-lg btn-block'),
            )
        )

    def clean_referral_code(self):
        referral_code = self.cleaned_data.get('referral_code')
        if referral_code:
            try:
                code = ReferralCode.objects.get(code=referral_code, is_used=False)
            except ReferralCode.DoesNotExist:
                raise forms.ValidationError("Invalid or already used referral code.")
        return referral_code

class ApplicationPersonalInfoForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['passport_photo', 'first_name', 'surname', 'other_name', 'date_of_birth',
                 'phone', 'email', 'address', 'lga', 'state_of_origin']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-4"><i class="fas fa-user"></i> Personal Information</h5>'),
            Row(
                Column('passport_photo', css_class='form-group col-md-12 mb-3'),
                css_class='form-row'
            ),
            Row(
                Column('first_name', css_class='form-group col-md-4 mb-3'),
                Column('surname', css_class='form-group col-md-4 mb-3'),
                Column('other_name', css_class='form-group col-md-4 mb-3'),
                css_class='form-row'
            ),
            Row(
                Column('date_of_birth', css_class='form-group col-md-6 mb-3'),
                Column('phone', css_class='form-group col-md-6 mb-3'),
                css_class='form-row'
            ),
            Field('email', css_class='form-control mb-3'),
            Field('address', css_class='form-control mb-3'),
            Row(
                Column('lga', css_class='form-group col-md-6 mb-3'),
                Column('state_of_origin', css_class='form-group col-md-6 mb-3'),
                css_class='form-row'
            ),
        )

class GuardianInfoForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['guardian_name', 'guardian_phone', 'guardian_address', 'guardian_relationship']
        widgets = {
            'guardian_address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-4"><i class="fas fa-users"></i> Guardian/Next of Kin Information</h5>'),
            Row(
                Column('guardian_name', css_class='form-group col-md-6 mb-3'),
                Column('guardian_phone', css_class='form-group col-md-6 mb-3'),
                css_class='form-row'
            ),
            Field('guardian_address', css_class='form-control mb-3'),
            Field('guardian_relationship', css_class='form-control mb-3'),
        )

class SchoolAttendedForm(forms.ModelForm):
    class Meta:
        model = SchoolAttended
        fields = ['school_name', 'from_year', 'to_year']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class SSCEResultForm(forms.ModelForm):
    class Meta:
        model = SSCEResult
        fields = ['sitting_number', 'exam_type', 'exam_number', 'registration_number',
                 'centre_number', 'centre_name', 'year',
                 'english_grade', 'mathematics_grade', 'biology_grade', 'chemistry_grade', 'physics_grade',
                 'subject_1', 'subject_1_grade', 'subject_2', 'subject_2_grade',
                 'subject_3', 'subject_3_grade', 'subject_4', 'subject_4_grade']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class CourseSelectionForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['first_choice', 'second_choice']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-4"><i class="fas fa-graduation-cap"></i> Course Selection</h5>'),
            Field('first_choice', css_class='form-control mb-3'),
            Field('second_choice', css_class='form-control mb-3'),
        )

    def clean(self):
        cleaned_data = super().clean()
        first_choice = cleaned_data.get('first_choice')
        second_choice = cleaned_data.get('second_choice')
        
        if first_choice and second_choice and first_choice == second_choice:
            raise forms.ValidationError("First choice and second choice cannot be the same.")
        
        return cleaned_data

class DeclarationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['declaration_text']
        widgets = {
            'declaration_text': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-4"><i class="fas fa-file-signature"></i> Declaration</h5>'),
            HTML('<p class="text-muted mb-3">Please type your full name and the following declaration:</p>'),
            HTML('<p class="font-italic">"I hereby declare that the information provided in this application form is true and correct to the best of my knowledge. I understand that any false information may lead to the cancellation of my admission."</p>'),
            Field('declaration_text', css_class='form-control mb-3',
                 placeholder='Type your full name and the declaration statement above...'),
        )

class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedDocument
        fields = ['document_type', 'document']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'