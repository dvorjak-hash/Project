from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .models import Task, Project, Calendar, Tag, UserSettings, Todo
from .forms import TaskForm, ProjectForm, CalendarForm, UserSettingsForm, TodoForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import date, timedelta
import calendar as calendar_module

# Create your views here.

def _parse_tags(user, raw_tags):
    if not raw_tags:
        return []
    names = [name.strip() for name in raw_tags.split(",") if name.strip()]
    tags = []
    for name in names:
        tag, _ = Tag.objects.get_or_create(user=user, name=name)
        tags.append(tag)
    return tags


def _add_months(value_date, months=1):
    month = value_date.month - 1 + months
    year = value_date.year + month // 12
    month = month % 12 + 1
    day = min(value_date.day, calendar_module.monthrange(year, month)[1])
    return date(year, month, day)


def _get_next_recurrence_date(task):
    if task.recurrence == Task.RECURRENCE_DAILY:
        return task.date + timedelta(days=1)
    if task.recurrence == Task.RECURRENCE_WEEKLY:
        return task.date + timedelta(days=7)
    if task.recurrence == Task.RECURRENCE_MONTHLY:
        return _add_months(task.date, 1)
    return None


def _create_next_recurring_task(task):
    next_date = _get_next_recurrence_date(task)
    if not next_date or not task.repeat_until:
        return
    if next_date > task.repeat_until:
        return
    if Task.objects.filter(project=task.project, title=task.title, date=next_date, user=task.user).exists():
        return

    new_task = Task.objects.create(
        project=task.project,
        user=task.user,
        title=task.title,
        description=task.description,
        date=next_date,
        start_time=task.start_time,
        end_time=task.end_time,
        priority=task.priority,
        recurrence=task.recurrence,
        repeat_until=task.repeat_until,
        completed=False,
    )
    new_task.tags.set(task.tags.all())


@login_required
def dashboard(request):
    """Hlavní dashboard s přehledem aktivit"""
    user = request.user

    # Získání kalendáře uživatele
    calendar = Calendar.objects.filter(user=user).first()
    if not calendar:
        calendar = Calendar.objects.create(user=user, field="Můj kalendář")

    # Statistiky
    total_projects = Project.objects.filter(user=user).count()
    total_tasks = Task.objects.filter(user=user).count()
    completed_tasks = Task.objects.filter(user=user, completed=True).count()
    pending_tasks = total_tasks - completed_tasks
    total_todos = Todo.objects.filter(user=user).count()
    completed_todos = Todo.objects.filter(user=user, completed=True).count()
    pending_todos = total_todos - completed_todos

    # Nedávné úkoly (posledních 7 dní)
    week_ago = timezone.now() - timedelta(days=7)
    recent_tasks = Task.objects.filter(
        user=user,
        created_at__gte=week_ago
    ).order_by('-created_at')[:5]

    # Dnešní úkoly
    today_tasks = Task.objects.filter(
        user=user,
        date=date.today()
    ).order_by('start_time')

    # Dnešní Todo
    today_todos = Todo.objects.filter(
        user=user,
        due_date=date.today()
    ).order_by('created_at')

    # Probíhající projekty
    current_projects = Project.objects.filter(
        user=user,
        start_date__lte=date.today(),
        end_date__gte=date.today()
    ).order_by('end_date')

    # Nadcházející a po termínu
    upcoming_projects = Project.objects.filter(
        user=user,
        start_date__gt=date.today()
    ).order_by('start_date')

    overdue_projects = Project.objects.filter(
        user=user,
        end_date__lt=date.today()
    ).order_by('-end_date')

    # Úkoly k dokončení a přehledné seznamy
    pending_tasks_list = Task.objects.filter(
        user=user,
        completed=False
    ).order_by('date', 'start_time')[:6]

    overdue_tasks = Task.objects.filter(
        user=user,
        completed=False,
        date__lt=date.today()
    ).order_by('date', 'start_time')[:6]

    recent_completed_tasks = Task.objects.filter(
        user=user,
        completed=True
    ).order_by('-date')[:6]

    todo_pending = Todo.objects.filter(
        user=user,
        completed=False
    ).order_by('due_date')[:6]

    todo_completed = Todo.objects.filter(
        user=user,
        completed=True
    ).order_by('-due_date')[:6]

    context = {
        'calendar': calendar,
        'total_projects': total_projects,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks.count(),
        'total_todos': total_todos,
        'completed_todos': completed_todos,
        'pending_todos': pending_todos,
        'recent_tasks': recent_tasks,
        'today_tasks': today_tasks,
        'current_projects': current_projects,
        'upcoming_projects': upcoming_projects,
        'overdue_projects': overdue_projects,
        'pending_tasks_list': pending_tasks_list,
        'overdue_tasks_list': overdue_tasks,
        'recent_completed_tasks': recent_completed_tasks,
        'todo_pending': todo_pending,
        'todo_completed': todo_completed,
        'today_todos': today_todos,
    }

    return render(request, "tasks/dashboard.html", context)


@login_required
def create_calendar(request):
    if request.method == "POST":
        form = CalendarForm(request.POST)
        if form.is_valid():
            calendar = form.save(commit=False)
            calendar.user = request.user
            calendar.save()
            return redirect("calendar_list")
    else:
        form = CalendarForm()

    return render(request, "tasks/create_calendar.html", {"form": form})


@login_required
def calendar_view(request):
    return render(request, "tasks/calendar_view.html")


@login_required
def calendar_events(request):
    user = request.user
    calendar = Calendar.objects.filter(user=user).first()
    
    if not calendar:
        return JsonResponse([], safe=False)
    
    projects = Project.objects.filter(calendar=calendar)
    today = date.today()

    events = []
    for project in projects:
        # Výpočet urgency podle zbývajícího času
        total_days = (project.end_date - project.start_date).days
        if total_days <= 0:
            remaining_percentage = 0
        else:
            remaining_days = (project.end_date - today).days
            remaining_percentage = max(0, remaining_days / total_days)
        
        if remaining_percentage > 0.5:
            class_name = "urgency-low"  # zelená - nízká urgentnost
        elif remaining_percentage > 0.25:
            class_name = "urgency-medium"  # oranžová - střední urgentnost
        else:
            class_name = "urgency-high"  # červená - vysoká urgentnost
        
        # Jednodušší název s počtem zbývajících dní
        remaining_days = max(0, (project.end_date - today).days)
        title = f"{project.title} ({remaining_days} dní)"
        
        events.append({
            "id": project.id,
            "title": title,
            "start": project.start_date.isoformat(),
            "end": project.end_date.isoformat(),
            "url": f"/tasks/projects/{project.id}/",
            "className": class_name,
            "extendedProps": {
                "description": project.description,
                "remaining_days": remaining_days,
                "total_days": total_days,
                "remaining_percentage": remaining_percentage,
            }
        })

    return JsonResponse(events, safe=False)



@login_required
def task_list(request):
    user = request.user

    # Získání parametrů filtru a třídění z URL
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    project_filter = request.GET.get('project', 'all')
    tag_filter = request.GET.get('tag', 'all')
    sort_by = request.GET.get('sort', 'date')

    # Základní queryset - pouze úkoly uživatele
    tasks = Task.objects.filter(user=user)

    # Aplikace filtrů
    if status_filter == 'completed':
        tasks = tasks.filter(completed=True)
    elif status_filter == 'pending':
        tasks = tasks.filter(completed=False)
    else:
        settings = getattr(request.user, 'usersettings', None)
        if settings and not settings.show_completed_tasks:
            tasks = tasks.filter(completed=False)

    if priority_filter != 'all':
        try:
            tasks = tasks.filter(priority=int(priority_filter))
        except ValueError:
            pass

    if project_filter != 'all':
        tasks = tasks.filter(project_id=project_filter)

    if tag_filter != 'all':
        tasks = tasks.filter(tags__name=tag_filter)

    # Aplikace třídění
    if sort_by == 'date':
        tasks = tasks.order_by('date', 'start_time')
    elif sort_by == 'priority':
        tasks = tasks.order_by('priority', 'date')
    elif sort_by == 'title':
        tasks = tasks.order_by('title')
    elif sort_by == 'project':
        tasks = tasks.order_by('project__title', 'date')
    elif sort_by == 'status':
        tasks = tasks.order_by('completed', 'date')

    # Získání projektů a tagů pro filtr
    projects = Project.objects.filter(user=user)
    tags = Tag.objects.filter(user=user).order_by('name')

    # Statistiky pro dashboard-like informace
    total_tasks = Task.objects.filter(user=user).count()
    completed_count = Task.objects.filter(user=user, completed=True).count()
    pending_count = total_tasks - completed_count

    context = {
        'tasks': tasks,
        'projects': projects,
        'tags': tags,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'project_filter': project_filter,
        'tag_filter': tag_filter,
        'sort_by': sort_by,
        'total_tasks': total_tasks,
        'completed_count': completed_count,
        'pending_count': pending_count,
    }

    return render(request, "tasks/task_list.html", context)

@login_required
def create_task(request, project_id=None):
    user = request.user
    
    # Pokud je zadán project_id, získáme projekt
    project = None
    if project_id:
        project = get_object_or_404(Project, id=project_id, user=user)
    
    # Získáme seznam projektů pro výběr v formuláři
    projects = Project.objects.filter(user=user)

    date = request.GET.get("date")

    if request.method == "POST":
        post_data = request.POST.copy()
        if project:
            post_data['project'] = project.id
        form = TaskForm(post_data, user=user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = user
            if project:
                task.project = project
            task.save()

            tag_names = form.cleaned_data.get("tag_names", "")
            task.tags.set(_parse_tags(user, tag_names))

            if task.completed and task.recurrence != Task.RECURRENCE_NONE:
                _create_next_recurring_task(task)

            return redirect("tasks:project_detail", pk=task.project.id)
    else:
        initial = {}
        if date:
            initial["date"] = date
        settings = getattr(user, 'usersettings', None)
        if settings:
            initial.setdefault("priority", settings.default_priority)
            initial.setdefault("recurrence", settings.default_recurrence)

        form = TaskForm(initial=initial, user=user)
        
        # Pokud je projekt zadán v URL, nastavíme jej jako výchozí
        if project:
            form.fields['project'].initial = project

    return render(request, "tasks/create_task.html", {
        "form": form,
        "project": project,
        "projects": projects
    })

@login_required
def edit_task(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            updated_task = form.save(commit=False)
            updated_task.user = request.user
            updated_task.save()
            
            tag_names = form.cleaned_data.get("tag_names", "")
            updated_task.tags.set(_parse_tags(request.user, tag_names))
            
            return redirect("tasks:task_list")
    else:
        form = TaskForm(instance=task, user=request.user)
    
    return render(request, "tasks/edit_task.html", {
        "form": form,
        "task": task
    })

@login_required
def delete_task(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    
    if request.method == "POST":
        task.delete()
        return redirect("tasks:task_list")
    
    return render(request, "tasks/delete_task.html", {"task": task})




def project_list(request):
    projects = Project.objects.filter(user=request.user)

    return render(request, "tasks/project_list.html", {
        "projects": projects
    })


@login_required
def user_settings(request):
    settings, _ = UserSettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            return redirect("tasks:user_settings")
    else:
        form = UserSettingsForm(instance=settings)

    return render(request, "tasks/user_settings.html", {"form": form})


@login_required
def create_project(request):
    user = request.user
    calendar = Calendar.objects.filter(user=user).first()

    if not calendar:
        calendar = Calendar.objects.create(user=user, field="Můj kalendář")

    # Zpracuj start_date z URL, pokud existuje
    start_date = request.GET.get("start_date")

    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = user
            project.calendar = calendar   
            project.save()
            return redirect("tasks:project_detail", pk=project.id)
    else:
        # Pokud je start_date v URL, použij jej jako výchozí
        if start_date:
            form = ProjectForm(initial={"start_date": start_date})
        else:
            form = ProjectForm()

    return render(request, "tasks/create_project.html", {
        "form": form
    })

@login_required
@csrf_exempt
def create_project_from_calendar(request):
    if request.method == "POST":
        data = json.loads(request.body)

        calendar, created = Calendar.objects.get_or_create(user=request.user)

        project = Project.objects.create(
            title=data["title"],
            start_date=parse_date(data["start_date"]),
            end_date=parse_date(data["end_date"]),
            calendar=calendar,
            user=request.user
        )

        return JsonResponse({"status": "ok"})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk, user=request.user)
    return render(request, "tasks/project_detail.html", {"project": project})

@login_required
def edit_project(request, pk):
    project = get_object_or_404(Project, pk=pk, user=request.user)
    calendar, created = Calendar.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            updated_project = form.save(commit=False)
            updated_project.user = request.user
            updated_project.calendar = calendar
            updated_project.save()
            return redirect("tasks:project_detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(request, "tasks/edit_project.html", {
        "form": form,
        "project": project
    })

@login_required
def delete_project(request, pk):
    project = get_object_or_404(Project, pk=pk, user=request.user)

    if request.method == "POST":
        project.delete()
        return redirect("tasks:project_list")

    return render(request, "tasks/delete_project.html", {"project": project})


def home(request):
    calendar, created = Calendar.objects.get_or_create(user=request.user)
    return render(request, "tasks/home.html", {"calendar": calendar})
@login_required
def todo_list(request):
    todos = Todo.objects.filter(user=request.user).order_by('due_date')
    return render(request, 'tasks/todo_list.html', {'todos': todos})

@login_required
def create_todo(request):
    if request.method == 'POST':
        form = TodoForm(request.POST)
        if form.is_valid():
            todo = form.save(commit=False)
            todo.user = request.user
            todo.save()
            return redirect('tasks:todo_list')
    else:
        form = TodoForm()
    return render(request, 'tasks/create_todo.html', {'form': form})

@login_required
def edit_todo(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TodoForm(request.POST, instance=todo)
        if form.is_valid():
            form.save()
            return redirect('tasks:todo_list')
    else:
        form = TodoForm(instance=todo)
    return render(request, 'tasks/edit_todo.html', {'form': form, 'todo': todo})

@login_required
def delete_todo(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    if request.method == 'POST':
        todo.delete()
        return redirect('tasks:todo_list')
    return render(request, 'tasks/delete_todo.html', {'todo': todo})

@login_required
def toggle_todo_completed(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    todo.completed = not todo.completed
    todo.save()
    return redirect('tasks:todo_list')
