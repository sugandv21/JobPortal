from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import Job, Application, Profile

User = get_user_model()


class RegisterForm(UserCreationForm):
    """
    Extended registration form:
    - collects email
    - optional is_employer checkbox and company_name (stored on Profile)
    """
    email = forms.EmailField(required=True)
    is_employer = forms.BooleanField(
        required=False,
        initial=False,
        label="Register as employer",
        help_text="Tick if you are an employer who will post jobs."
    )
    company_name = forms.CharField(
        required=False,
        max_length=255,
        label="Company name (optional)",
        help_text="Optional company name for employer accounts."
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2", "is_employer", "company_name")

    def save(self, commit=True):
        user = super().save(commit=commit)
        # save email
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()

        # ensure Profile exists and update fields if provided
        is_employer = self.cleaned_data.get("is_employer", False)
        company_name = self.cleaned_data.get("company_name", "").strip()
        profile, _ = Profile.objects.get_or_create(user=user)
        if is_employer:
            profile.is_employer = True
        if company_name:
            profile.company_name = company_name
        profile.save()

        return user


class JobSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Keyword", widget=forms.TextInput(attrs={"placeholder": "keyword"}))
    location = forms.CharField(required=False, label="Location", widget=forms.TextInput(attrs={"placeholder": "location"}))


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ("title", "company", "description", "location")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "title": forms.TextInput(attrs={"placeholder": "Job title"}),
            "company": forms.TextInput(attrs={"placeholder": "Company name"}),
            "location": forms.TextInput(attrs={"placeholder": "City, State, Country"}),
        }


class ApplicationForm(forms.ModelForm):
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB

    class Meta:
        model = Application
        fields = ("resume", "cover_letter")
        widgets = {
            "cover_letter": forms.Textarea(attrs={"rows": 5, "placeholder": "Optional cover letter"}),
        }

    def clean_resume(self):
        resume = self.cleaned_data.get("resume")
        if not resume:
            raise forms.ValidationError("Please upload your resume.")
        if resume.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("Resume file size must be under 5 MB.")
        return resume
