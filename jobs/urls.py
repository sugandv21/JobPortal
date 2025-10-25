from django.urls import path
from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.JobListView.as_view(), name="job_list"),
    path("job/create/", views.JobCreateView.as_view(), name="job_create"),
    path("job/<int:pk>/", views.JobDetailView.as_view(), name="job_detail"),
    path("job/<int:pk>/update/", views.JobUpdateView.as_view(), name="job_update"),
    path("job/<int:pk>/delete/", views.JobDeleteView.as_view(), name="job_delete"),
    path("job/<int:pk>/apply/", views.ApplyJobView.as_view(), name="job_apply"),
    path("application/<int:pk>/withdraw/", views.WithdrawApplicationView.as_view(), name="withdraw_application"),

    path("application/<int:pk>/shortlist/", views.ShortlistApplicationView.as_view(), name="application_shortlist"),
    path("application/<int:application_pk>/interview/schedule/", views.InterviewCreateView.as_view(), name="interview_create"),
    path("interview/<int:pk>/edit/", views.InterviewUpdateView.as_view(), name="interview_update"),
    path("interview/<int:pk>/cancel/", views.InterviewCancelView.as_view(), name="interview_cancel"),

    path("register/", views.RegisterView.as_view(), name="register"),
]
