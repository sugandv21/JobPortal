from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.urls import reverse

User = get_user_model()

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    is_employer = models.BooleanField(default=False)
    company_name = models.CharField(max_length=255, blank=True)
    def __str__(self): return f"Profile({self.user.username})"

class Job(models.Model):
    poster = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posted_jobs")
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["title"]), models.Index(fields=["company"]), models.Index(fields=["location"])]
    def __str__(self): return f"{self.title} at {self.company}"
    def get_absolute_url(self): return reverse("jobs:job_detail", kwargs={"pk": self.pk})

def resume_upload_to(instance, filename):
    return f"resumes/user_{instance.applicant.id}/{filename}"

class Application(models.Model):
    STATUS_APPLIED   = "applied"
    STATUS_REVIEW    = "review"
    STATUS_SHORTLIST = "shortlisted"
    STATUS_ACCEPTED  = "accepted"
    STATUS_REJECTED  = "rejected"
    STATUS_WITHDRAWN = "withdrawn"

    STATUS_CHOICES = [
        (STATUS_APPLIED, "Applied"),
        (STATUS_REVIEW, "Under Review"),
        (STATUS_SHORTLIST, "Shortlisted"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="applications")
    resume = models.FileField(
        upload_to=resume_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "doc", "docx"])],
        help_text="Upload resume in PDF, DOC or DOCX format.",
    )
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_APPLIED)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("job", "applicant")
        ordering = ["-applied_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["applied_at"])]

    def __str__(self): return f"Application(job={self.job.title!r}, applicant={self.applicant.username!r})"
    def get_resume_filename(self) -> str: return self.resume.name.split("/")[-1]

class Interview(models.Model):
    MODE_CHOICES = [("in_person","In person"),("phone","Phone"),("video","Video")]
    STATUS_CHOICES = [("scheduled","Scheduled"),("rescheduled","Rescheduled"),("completed","Completed"),("canceled","Canceled")]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="interviews")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_interviews")
    scheduled_at = models.DateTimeField()
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="video")
    location = models.CharField(max_length=255, blank=True, help_text="Office address (for in-person) or leave blank.")
    meet_link = models.CharField(max_length=255, blank=True, help_text="Video/Phone meeting link or dial-in.")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    invite_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"Interview({self.application.applicant.username} - {self.application.job.title} @ {self.scheduled_at})"
