from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Calendar(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    field = models.CharField(max_length=100)


class Tag(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

    @property
    def completed_task_count(self):
        return self.tasks.filter(completed=True).count()

    @property
    def pending_task_count(self):
        return self.tasks.filter(completed=False).count()

    @property
    def remaining_days(self):
        from datetime import date
        today = date.today()
        return max(0, (self.end_date - today).days)


class Task(models.Model):
    PRIORITY_HIGH = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_LOW = 3

    PRIORITY_CHOICES = [
        (PRIORITY_HIGH, "Vysoká"),
        (PRIORITY_MEDIUM, "Střední"),
        (PRIORITY_LOW, "Nízká"),
    ]

    RECURRENCE_NONE = "none"
    RECURRENCE_DAILY = "daily"
    RECURRENCE_WEEKLY = "weekly"
    RECURRENCE_MONTHLY = "monthly"

    RECURRENCE_CHOICES = [
        (RECURRENCE_NONE, "Žádné"),
        (RECURRENCE_DAILY, "Denně"),
        (RECURRENCE_WEEKLY, "Týdně"),
        (RECURRENCE_MONTHLY, "Měsíčně"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default=RECURRENCE_NONE)
    repeat_until = models.DateField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def priority_css(self):
        return {
            self.PRIORITY_HIGH: "high",
            self.PRIORITY_MEDIUM: "medium",
            self.PRIORITY_LOW: "low",
        }.get(self.priority, "medium")

    @property
    def tag_names(self):
        return ", ".join(self.tags.values_list("name", flat=True))


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    default_priority = models.IntegerField(choices=Task.PRIORITY_CHOICES, default=Task.PRIORITY_MEDIUM)
    default_recurrence = models.CharField(max_length=10, choices=Task.RECURRENCE_CHOICES, default=Task.RECURRENCE_NONE)
    show_completed_tasks = models.BooleanField(default=True)

    def __str__(self):
        return f"Nastavení uživatele {self.user.username}"


class Reminder(models.Model):
    remind_at = models.DateTimeField()

    text = models.CharField(max_length=200)

    task = models.ForeignKey(Task, on_delete=models.CASCADE)

    def __str__(self):
        return self.text


class Todo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title