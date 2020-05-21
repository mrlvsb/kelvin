import json
import os
import io
import csv

import yaml

from django.shortcuts import render, redirect
from django.conf import settings
from django import forms
from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test

from .models import Answer
from common.utils import is_teacher

base = os.path.join(settings.BASE_DIR, "survey", "surveys")

types = {
    'textarea': (forms.CharField, {'widget': forms.Textarea({
        'rows': 4,
        'class': 'form-control'
    })}),
    'line': (forms.CharField, {'widget': forms.TextInput({
        'class': 'form-control'
    })}),
    'integer': (forms.IntegerField, {'widget': forms.NumberInput({
        'class': 'form-control'
    })}),
    'radio': (forms.ChoiceField, {'widget': forms.RadioSelect({'class': 'form-check-input'})}),
    'select': (forms.ChoiceField, {}),
    'multiselect': (forms.MultipleChoiceField, {}),
    'checkboxes': (forms.MultipleChoiceField, {'widget': forms.CheckboxSelectMultiple({'class': 'form-check-input'})}),
}

class SurveyError(Exception):
    pass

def survey_read(path, user):
    try:
        with open(os.path.join(base, f"{path}.yaml")) as f:
            conf = yaml.load(f.read(), Loader=yaml.SafeLoader)
            conf['name'] = path
            if is_teacher(user) or ('active' in conf and conf['active']):
                if 'questions' not in conf or not isinstance(conf['questions'], list):
                    raise SurveyError(f"Survey '{path}' does not contain list of questions in yaml")
                return conf
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise SurveyError(e)

def available_surveys(user):
    available = []
    for path in os.listdir(base):
        name = ".".join(path.split('.')[:-1])
        conf = survey_read(name, user)
        if conf:
            conf['name'] = name
            if 'title' not in conf:
                conf['title'] = conf['name']
            available.append(conf)

    return available

def create_survey_form(request, conf, defaults):
    form = forms.Form(request.POST if request.method == 'POST' else defaults)

    for q in conf['questions']:
        qtype = q.get('type', None)
        if qtype not in types:
            raise SurveyError(f"Invalid type '{qtype}'. Available types: {', '.join(types.keys())}")

        field, args = types[qtype]

        if 'question' not in q:
            raise SurveyError("Missing question text")
        args['label'] = q['question']
        args['required'] = True

        for k, v in q.items():
            if k not in ['name', 'type', 'question']:
                if k == 'choices':
                    v = v.items()
                args[k] = v

        try:
            form.fields[q['name']] = field(**args)
        except TypeError as e:
            raise SurveyError(f"Field {q['name']}: {e}")

    return form

@login_required()
def survey_list(request):
    surveys = available_surveys(request.user)
    if len(surveys) == 1:
        return redirect('survey_show', surveys[0]['name'])

    return render(request, 'list.html', {
        'surveys': surveys,
    })

@login_required()
def show(request, survey_file):
    try:
        conf = survey_read(survey_file, request.user)

        editable = 'editable' in conf and conf['editable']
        answered = Answer.objects.filter(student=request.user, survey_name=survey_file)

        if answered and not editable:
            return render(request, 'survey.html', {'survey': conf})

        defaults = None
        if answered:
            defaults = json.loads(answered[0].answers)

        form = create_survey_form(request, conf, defaults)
        if request.method == 'POST' and form.is_valid():
            Answer.objects.update_or_create(
                    student_id=request.user.id,
                    survey_name=conf['name'],
                    defaults={
                        "answers": json.dumps(form.cleaned_data)
                    }
            )
            return redirect(request.path_info)

        return render(request, "survey.html", {
            "form": form,
            "survey": conf,
        })
    except FileNotFoundError as e:
        raise Http404()
    except SurveyError as e:
        if not is_teacher(request.user):
            raise e
        return HttpResponse(e)

@user_passes_test(is_teacher)
def show_csv(request, survey_file):
    answers = []
    for answer in Answer.objects.filter(survey_name=survey_file):
        data = {}
        data['login'] = answer.student.username
        data['submitted'] = answer.created_at
        for k, v in json.loads(answer.answers).items():
            if isinstance(v, list):
                v = ",".join(v)
            data[k] = v

        answers.append(data)

    conf = survey_read(survey_file, request.user)
    if not answers or not conf:
        return HttpResponse(status=204)

    with io.StringIO() as out:
        w = csv.DictWriter(out, fieldnames=['login', 'submitted'] + [q['name'] for q in conf['questions']])
        w.writeheader()

        for answer in answers:
            w.writerow(answer)

        response = HttpResponse(out.getvalue(), 'text/plain; charset=utf-8')
        return response

@user_passes_test(is_teacher)
def show_edison_csv(request, survey_file):
    """
    Outputs CSV with just logins and 'A' to mark the task as done in EdISon.
    """
    answers = []
    for answer in Answer.objects.filter(survey_name=survey_file):
        data = {}
        data['login'] = answer.student.username
        data['done'] = 'A'

        answers.append(data)

    conf = survey_read(survey_file, request.user)
    if not answers or not conf:
        return HttpResponse(status=204)

    with io.StringIO() as out:
        w = csv.DictWriter(out, fieldnames=['login', 'done'], delimiter=';')

        for answer in answers:
            w.writerow(answer)

        response = HttpResponse(out.getvalue(), 'text/plain; charset=utf-8')
        return response
