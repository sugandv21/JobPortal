from django.contrib import admin
from .models import Profile, Job, Application


class ApplicationInline(admin.TabularInline):
    model = Application
    extra = 0
    readonly_fields = ("applicant", "resume", "status", "applied_at")
    fields = ("applicant", "resume", "status", "applied_at")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "poster", "location", "created_at")
    search_fields = ("title", "company", "description", "location")
    list_filter = ("location", "created_at")
    inlines = [ApplicationInline]
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("job", "applicant", "status", "applied_at")
    list_filter = ("status", "applied_at")
    search_fields = ("job__title", "applicant__username", "applicant__email")
    readonly_fields = ("applied_at",)
    actions = ["mark_as_review", "mark_as_accepted", "mark_as_rejected"]

    def mark_as_review(self, request, queryset):
        updated = queryset.update(status="review")
        self.message_user(request, f"{updated} application(s) marked as Under Review.")
    mark_as_review.short_description = "Mark selected applications as Under Review"

    def mark_as_accepted(self, request, queryset):
        updated = queryset.update(status="accepted")
        self.message_user(request, f"{updated} application(s) marked as Accepted.")
    mark_as_accepted.short_description = "Mark selected applications as Accepted"

    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status="rejected")
        self.message_user(request, f"{updated} application(s) marked as Rejected.")
    mark_as_rejected.short_description = "Mark selected applications as Rejected"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_employer", "company_name")
    list_filter = ("is_employer",)
    search_fields = ("user__username", "company_name")
