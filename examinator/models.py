import os
import glob
import datetime
import subprocess
import lxml.html as html
import re
import json

from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User

BASE = "exams"

class ExamException(Exception):
    pass

class Exam:
    def __init__(self, exam_id):
        if '..' in exam_id:
            raise ExamException(f"[{exam_id}] Invalid path")

        self.id = exam_id
        self.students = []
        self.begin = None
        self.dir = os.path.join(BASE, exam_id)
        self.subject = exam_id.split('/')[0]
        self.questions = None
        self.student_objs_cache = None

        try:
            with open(os.path.join(self.dir, "description")) as f:
                lines = [i.strip() for i in f.read().splitlines()]
                self.begin = datetime.datetime.strptime(lines[0], "%d. %m. %Y %H:%M")
                self.students = [stud.strip() for stud in lines[1:] if len(stud.strip())]
        except FileNotFoundError as e:
            raise ExamException(f"[{exam_id}] Exam file does not exist: {e}")

    def is_finished(self):
        return os.path.exists(os.path.join(self.dir, "finished"))

    def answer_filename(self, student, question):
        return os.path.join(self.dir, student, f"{question:02}")

    def ensure_dir(self, student):
        base = os.path.join(self.dir, student)
        try:
            os.mkdir(base)
        except FileExistsError:
            pass

    def student_objs(self):
        if self.student_objs_cache:
            return self.student_objs_cache

        students = []
        for stud in self.students:
            students.append((stud, User.objects.filter(username=stud).first()))

        self.student_objs_cache = students
        return students

    def prepare_start(self):
        for student in self.students:
            self.ensure_dir(student)
            for i in range(1, len(self.get_questions()) + 1):
                with open(self.answer_filename(student, i), "a") as f:
                    pass

    def finish(self):
        with open(os.path.join(self.dir, "finished"), "w")as f:
            f.write("")

    def save_answer(self, student, question_num, answer):
        self.ensure_dir(student)
        with open(self.answer_filename(student, question_num), "w") as f:
            if answer and answer[-1] != "\n":
                answer += "\n"
            f.write(answer)

    def get_questions(self):
        if self.questions:
            return self.questions

        with open(os.path.join(BASE, self.id, "questions.md")) as markdown:
            p = subprocess.Popen(["pandoc", "--self-contained", '--metadata', 'title=exam'], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.dir)
            out, err = p.communicate(input=markdown.read().encode('utf-8'))
            if p.returncode != 0:
                return [{'question': f'<span style="color: red; font-size: 20px">{err.decode("utf-8")}</span>', 'seconds': 1000}]
            out = out.decode('utf-8')
            root = html.fromstring(out)
            questions = root.cssselect('body > ol > li')

            seconds = 3 * 60
            self.questions = []
            for question in questions:
                s = html.tostring(question, pretty_print=True).decode('utf-8')
                s = re.sub(r'^\s*<li>', '', s)
                s = re.sub(r'</li>\s*$', '', s)
                s = s.strip()
 
                match = re.match(r"^(<p>)?\[(\d+)\]", s)
                if match:
                    seconds = int(match.group(2))
                    s = re.sub(r"^(<p>)?\[(\d+)\]\s*", '\\1', s)

                self.questions.append({
                        "question": s.strip(),
                        "seconds": seconds,
                })

            return self.questions

    def get_answers(self, student):
        answers = []

        p = []
        try:
            with open(os.path.join(self.dir, student, "points.json")) as f:
                p = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            pass

        for i in range(1, len(self.get_questions()) + 1):
            result = {}
            result['answer'] = self.get_student_answer(student, i)
            if len(p) >= i:
                result = {**result, **p[i - 1]}

            answers.append(result)
        return answers

    def save_points(self, student, question, points, note):
        path = os.path.join(self.dir, student, "points.json")

        data = [{} for i in range(len(self.get_questions()))]
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            pass

        data[question - 1] = {
            'points': points,
            'note': note
        }

        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False)

    def get_student_answer(self, student, question):
        try:
            with open(self.answer_filename(student, question)) as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def save_upload(self, student, filename, data):
        filename = filename.replace('..', '').replace('/', '_')

        base = os.path.join(self.dir, student, "uploads")
        try:
            os.mkdir(base)
        except FileExistsError:
            pass
        with open(os.path.join(base, filename), "wb") as f:
            f.write(data)

    def get_uploads(self, student):
        base = os.path.join(self.dir, student, "uploads")
        try:
            return [{
                'filename': f,
                'url': reverse('exam_upload', args=[self.id, student, f]), 
            } for f in os.listdir(base)]
        except FileNotFoundError:
            pass

    def add_log(self, student, data):
        self.ensure_dir(student)
        with open(os.path.join(self.dir, student, "log.json"), "a") as f:
            json.dump(data, f, ensure_ascii=False)
            f.write("\n")



def all_exams():
    exams = []
    for d in glob.glob(BASE + "/**/description", recursive=True):
        d = d[len(BASE)+1:]

        if d.split('/')[-2] == 'template':
            continue
        exams.append(Exam(os.path.dirname(d)))
    return sorted(exams, reverse=True, key=lambda exam: exam.dir.split('/')[1] + str(exam.begin.timestamp()))
