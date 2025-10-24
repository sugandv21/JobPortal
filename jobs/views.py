# jobs/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model

from .models import Job, Application, Profile
from .forms import RegisterForm, JobSearchForm, ApplicationForm, JobForm

User = get_user_model()


class RegisterView(CreateView):
    """
    Registration view: uses RegisterForm (which should create/update Profile).
    Sends a registration email on success and shows a success message.
    """
    form_class = RegisterForm
    template_name = "jobs/registration/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        user = form.save()
        # Ensure profile exists and set employer flag/company_name if provided
        profile, _ = Profile.objects.get_or_create(user=user)
        is_employer = form.cleaned_data.get("is_employer", False)
        company_name = form.cleaned_data.get("company_name", "").strip()
        if is_employer:
            profile.is_employer = True
        if company_name:
            profile.company_name = company_name
        profile.save()

        # Send registration email (don't block on failure)
        try:
            send_mail(
                subject="Welcome to JobPortal",
                message=f"Hi {user.username},\n\nThanks for registering at JobPortal.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            # log but continue
            print("Registration email error:", e)

        messages.success(self.request, "Registration successful. Please check your email for confirmation.")
        return super().form_valid(form)


class JobListView(ListView):
    model = Job
    template_name = "jobs/job_list.html"
    context_object_name = "jobs"
    paginate_by = 2

    def get_queryset(self):
        qs = super().get_queryset().order_by("-created_at")
        q = self.request.GET.get("q", "").strip()
        location = self.request.GET.get("location", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(description__icontains=q) | Q(company__icontains=q)
            )
        if location:
            qs = qs.filter(location__icontains=location)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_form"] = JobSearchForm(self.request.GET or None)
        return ctx


class JobDetailView(DetailView):
    model = Job
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        job = self.object
        ctx["applications"] = job.applications.all()
        ctx["has_applied"] = False
        if self.request.user.is_authenticated:
            ctx["has_applied"] = job.applications.filter(applicant=self.request.user).exists()
        return ctx


class JobCreateView(LoginRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def dispatch(self, request, *args, **kwargs):
        # Optionally restrict posting to employer users only
        try:
            if not request.user.profile.is_employer:
                messages.error(request, "Only employer accounts can post jobs.")
                return redirect("jobs:job_list")
        except Exception:
            # if profile missing, prevent posting
            messages.error(request, "Your account is not authorised to post jobs.")
            return redirect("jobs:job_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.poster = self.request.user
        return super().form_valid(form)


class JobUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def test_func(self):
        job = self.get_object()
        return job.poster == self.request.user


class JobDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Job
    template_name = "jobs/job_confirm_delete.html"
    success_url = reverse_lazy("jobs:job_list")

    def test_func(self):
        job = self.get_object()
        return job.poster == self.request.user



class ApplyJobView(LoginRequiredMixin, CreateView):
    model = Application
    form_class = ApplicationForm
    template_name = "jobs/apply_form.html"

    def dispatch(self, request, *args, **kwargs):
        # load the job
        self.job = get_object_or_404(Job, pk=kwargs.get("pk"))
        # prevent duplicate apply
        if Application.objects.filter(job=self.job, applicant=request.user).exists():
            messages.warning(request, "You have already applied to this job.")
            return redirect("jobs:job_detail", pk=self.job.pk)

        # optional: prevent employers from applying
        try:
            if request.user.profile.is_employer:
                messages.error(request, "Employer accounts cannot apply to jobs.")
                return redirect("jobs:job_detail", pk=self.job.pk)
        except Exception:
            # if profile missing, let it proceed (or adjust to your policy)
            pass

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["job"] = self.job
        return ctx

    def form_valid(self, form):
        # Attach job and applicant then save
        form.instance.job = self.job
        form.instance.applicant = self.request.user
        self.object = form.save()

        # --- EMAIL: send confirmation to applicant (if email exists) ---
        applicant_email = (self.request.user.email or "").strip()
        if applicant_email:
            try:
                send_mail(
                    subject=f"Application received for {self.job.title}",
                    message=(
                        f"Hi {self.request.user.username},\n\n"
                        f"Thanks for applying to \"{self.job.title}\" at {self.job.company}.\n\n"
                        "We have received your application and will review it shortly."
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[applicant_email],
                    fail_silently=False,  # set False while testing so errors are shown in console
                )
            except Exception as e:
                # log to console — you'll see this when running the dev server
                print("Error sending applicant confirmation email:", e)
        else:
            print("Skipping applicant email: no email address for user", self.request.user)

        # --- EMAIL: notify job poster / employer (if poster has email) ---
        employer_email = (self.job.poster.email or "").strip()
        if employer_email:
            try:
                send_mail(
                    subject=f"New application for {self.job.title}",
                    message=(
                        f"Hi {self.job.poster.username},\n\n"
                        f"{self.request.user.username} has applied to your job posting: \"{self.job.title}\".\n\n"
                        "Please login to review the application."
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[employer_email],
                    fail_silently=False,
                )
            except Exception as e:
                print("Error sending employer notification email:", e)
        else:
            print("Skipping employer notification: poster has no email for job id", self.job.pk)

        messages.success(self.request, "Your application was submitted successfully.")
        # explicit redirect to job detail - avoids requiring Application.get_absolute_url()
        return redirect("jobs:job_detail", pk=self.job.pk)


class WithdrawApplicationView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        application = get_object_or_404(Application, pk=pk, applicant=request.user)
        application.status = "withdrawn"
        application.save()
        messages.success(request, "Application withdrawn.")
        return redirect("jobs:job_detail", pk=application.job.pk)
