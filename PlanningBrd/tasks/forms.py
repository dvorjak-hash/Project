from django import forms
from .models import Task, Project, Calendar, Tag, UserSettings, Todo


class CalendarForm(forms.ModelForm):
    class Meta:
        model = Calendar
        fields = ["field"]


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "description", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ["default_priority", "default_recurrence", "show_completed_tasks"]


class TaskForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        required=True,
        label="Projekt"
    )
    tag_names = forms.CharField(
        required=False,
        label="Tagy",
        help_text="Zadejte tagy oddělené čárkou",
        widget=forms.TextInput(attrs={"placeholder": "např. práce, osobní"})
    )
    
    class Meta:
        model = Task
        fields = ["title", "description", "date", "start_time", "end_time", "priority", "recurrence", "repeat_until", "completed", "project"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "repeat_until": forms.DateInput(attrs={"type": "date"}),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['project'].queryset = Project.objects.filter(user=user)
            self.fields['project'].label = "Projekt"
        if self.instance and self.instance.pk:
            self.fields['tag_names'].initial = ", ".join(self.instance.tags.values_list("name", flat=True))

class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ["title", "description", "due_date", "completed"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
