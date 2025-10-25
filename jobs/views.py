# jobs/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model

from .models import Job, Application, Profile
from .forms import RegisterForm, JobSearchForm, ApplicationForm, JobForm

User = get_user_model()



from .models import Interview
from .forms import InterviewForm

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
        ctx["my_app"] = None
        if self.request.user.is_authenticated:
            ctx["has_applied"] = job.applications.filter(applicant=self.request.user).exists()
            # prepare the user's application for this job (or None)
            ctx["my_app"] = job.applications.filter(applicant=self.request.user).first()
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


class ShortlistApplicationView(LoginRequiredMixin, View):
    """Employer can mark an application as Shortlisted (and auto-email the candidate)."""
    def post(self, request, pk, *args, **kwargs):
        app = get_object_or_404(Application, pk=pk)
        if app.job.poster != request.user:
            messages.error(request, "You are not allowed to modify this application.")
            return redirect("jobs:job_detail", pk=app.job.pk)
        app.status = Application.STATUS_SHORTLIST
        app.save(update_fields=["status", "updated_at"])

        # notify candidate
        if app.applicant.email:
            try:
                send_mail(
                    subject=f"You’ve been shortlisted for {app.job.title}",
                    message=(
                        f"Hi {app.applicant.username},\n\n"
                        f"You have been shortlisted for \"{app.job.title}\" at {app.job.company}.\n"
                        "We will contact you with interview details soon."
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[app.applicant.email],
                    fail_silently=False,
                )
            except Exception as e:
                print("Shortlist email error:", e)

        messages.success(request, "Application marked as Shortlisted and candidate notified.")
        return redirect("jobs:job_detail", pk=app.job.pk)

class InterviewCreateView(LoginRequiredMixin, CreateView):
    model = Interview
    form_class = InterviewForm
    template_name = "jobs/interview_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.application = get_object_or_404(Application, pk=kwargs.get("application_pk"))
        # only the job poster can schedule
        if self.application.job.poster != request.user:
            messages.error(request, "Only the job poster can schedule interviews.")
            return redirect("jobs:job_detail", pk=self.application.job.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.application = self.application
        form.instance.created_by = self.request.user
        self.object = form.save()

        # email both applicant and employer
        applicant_email = (self.application.applicant.email or "").strip()
        employer_email = (self.application.job.poster.email or "").strip()
        when_str = timezone.localtime(self.object.scheduled_at).strftime("%b %d, %Y %I:%M %p")
        details = f"Mode: {self.object.get_mode_display()}\n"
        if self.object.location: details += f"Location: {self.object.location}\n"
        if self.object.meet_link: details += f"Link: {self.object.meet_link}\n"
        details += f"\nNotes:\n{self.object.notes or '-'}"

        subj = f"Interview scheduled for {self.application.job.title}"
        body_candidate = (
            f"Hi {self.application.applicant.username},\n\n"
            f"Your interview for \"{self.application.job.title}\" at {self.application.job.company} "
            f"is scheduled on {when_str}.\n\n{details}\n"
        )
        body_employer = (
            f"Hi {self.request.user.username},\n\n"
            f"You scheduled an interview with {self.application.applicant.username} for "
            f"\"{self.application.job.title}\" on {when_str}.\n\n{details}\n"
        )
        try:
            if applicant_email:
                send_mail(subj, body_candidate, getattr(settings,"DEFAULT_FROM_EMAIL", None), [applicant_email], fail_silently=False)
            if employer_email:
                send_mail(subj, body_employer, getattr(settings,"DEFAULT_FROM_EMAIL", None), [employer_email], fail_silently=False)
            self.object.invite_sent = True
            self.object.save(update_fields=["invite_sent"])
        except Exception as e:
            print("Interview email error:", e)

        messages.success(self.request, "Interview scheduled and notifications sent.")
        return redirect("jobs:job_detail", pk=self.application.job.pk)

class InterviewUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Interview
    form_class = InterviewForm
    template_name = "jobs/interview_form.html"

    def test_func(self):
        interview = self.get_object()
        return interview.application.job.poster == self.request.user

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "Interview updated.")
        return redirect("jobs:job_detail", pk=self.object.application.job.pk)

class InterviewCancelView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self, interview):  # helper
        return interview.application.job.poster == self.request.user

    def post(self, request, pk, *args, **kwargs):
        interview = get_object_or_404(Interview, pk=pk)
        if not self.test_func(interview):
            messages.error(request, "You cannot cancel this interview.")
            return redirect("jobs:job_detail", pk=interview.application.job.pk)
        interview.status = "canceled"
        interview.save(update_fields=["status","updated_at"])

        # notify candidate
        if interview.application.applicant.email:
            try:
                send_mail(
                    subject=f"Interview canceled: {interview.application.job.title}",
                    message=(
                        f"Hi {interview.application.applicant.username},\n\n"
                        f"The interview scheduled for \"{interview.application.job.title}\" has been canceled.\n"
                        "You may receive a new schedule soon."
                    ),
                    from_email=getattr(settings,"DEFAULT_FROM_EMAIL", None),
                    recipient_list=[interview.application.applicant.email],
                    fail_silently=False,
                )
            except Exception as e:
                print("Interview cancel email error:", e)

        messages.success(request, "Interview canceled and candidate notified.")
        return redirect("jobs:job_detail", pk=interview.application.job.pk)