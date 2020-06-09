import json
import os
import datetime
from channels.generic.websocket import WebsocketConsumer, AsyncJsonWebsocketConsumer, AsyncConsumer
from common.utils import is_teacher
from channels.db import database_sync_to_async

import time
import logging
import asyncio
import base64
from .models import Exam

logger = logging.getLogger("exams")

def key(exam):
    return f"exam:{exam.id}"

def exam_bcast_group(exam):
    return f"exam-{exam.id.replace('/', '_')}"

def exam_bcast_teacher_group(exam):
    return f"exam-{exam.id.replace('/', '_')}-teacher"

async def current_question(channel_layer, exam):
    async with channel_layer.connection(0) as conn:
        question_idx, time_end = await conn.hmget(key(exam), 'idx', 'time_end')
        if not question_idx:
            return None
        question_idx = int(question_idx.decode('utf-8'))

        questions = exam.get_questions()
        if question_idx - 1 >= len(questions):
            return None

        return {
            "question": questions[question_idx - 1]['question'],
            'seconds_left': max(0, int(int(time_end.decode('utf-8')) - time.time())),
            'current_question': question_idx,
        }

class BeatConsumer(AsyncConsumer):
    async def next_question(self, data):
        exam = Exam(data['exam_id'])
        logger.info(f"Starting exam {exam.id}")
        asyncio.create_task(self.schedule(exam))

    async def is_paused(self, exam):
        async with self.channel_layer.connection(0) as conn:
            return await conn.hexists(key(exam), "pause")

    async def schedule(self, exam):
        seconds = 0
        async with self.channel_layer.connection(0) as conn:
            cur = await conn.hget(key(exam), "idx")
            if cur:
                cur = int(cur.decode('utf-8'))
            else:
                cur = 1
                exam.prepare_start()

            logger.info(f"Scheduling next question {cur} for {exam.id}")

            seconds = exam.get_questions()[cur - 1]['seconds']

            pipe = conn.multi_exec()
            pipe.hincrby(key(exam), 'idx', 1)
            pipe.hset(key(exam), 'time_end', int(time.time() + seconds))
            current_idx, _ = await pipe.execute()

        if current_idx - 1 >= len(exam.get_questions()):
            logger.info(f"Exam {exam.id} finished")
            await self.channel_layer.group_send(exam_bcast_group(exam), {
                'type': 'change_state',
                'state': 'finished',
            })
            exam.finish()
            async with self.channel_layer.connection(0) as conn:
                await conn.delete(key(exam))
        else:
            # broadcast new question
            question = await current_question(self.channel_layer, exam)
            await self.channel_layer.group_send(exam_bcast_group(exam), {**{'type': 'question'}, **question})

            await asyncio.sleep(seconds + 1)
            if await self.is_paused(exam):
                return
            await self.schedule(exam)

def allow_teacher(fn):
    def _fn(self, *args, **kwargs):
        if not self.is_teacher:
            raise "nope"
        return fn(self, *args, **kwargs)
    return _fn

class ChatConsumer(AsyncJsonWebsocketConsumer):
    def student_key(self):
        return f"exam:{self.exam.id}:{self.scope['user']}"

    async def log(self, event, data = None):
        if not data:
            data = {}

        data['mutation'] = event
        data['event'] = event
        data['student'] = self.scope['user'].username
        data['timestamp'] = time.time()

        for k, v in data.items():
            if isinstance(v, bool):
                data[k] = 1 if v else 0

        self.exam.add_log(data['student'], data)

        async with self.channel_layer.connection(0) as conn:
            conn.xadd(key(self.exam) + ":stream", data)

        await self.channel_layer.group_send(exam_bcast_teacher_group(self.exam), {**data, **{
            'type': 'log_send',
        }})

    async def increment_sessions(self, by):
        async with self.channel_layer.connection(0) as conn:
            self.session_id = await conn.hincrby(self.student_key(), 'sessions', by)

    async def connect(self):
        exam_id = self.scope["url_route"]["kwargs"]["id"]
        self.exam = Exam(exam_id)
        self.is_teacher = await database_sync_to_async(is_teacher)(self.scope['user'])

        init = {
            "action": "init",
            "total_questions": len(self.exam.get_questions()),
            "state": "not_started",
            "expected_start": self.exam.begin.strftime('%d. %m. %Y %H:%M'),
        }

        question = await current_question(self.channel_layer, self.exam)
        if question:
            init = {**init, **question}
            async with self.channel_layer.connection(0) as conn:
                init['state'] = 'paused' if await conn.hexists(key(self.exam), 'pause') else 'running'

        if self.exam.is_finished():
            init['state'] = 'finished'


        if self.is_teacher:
            students = []
            for s in self.exam.students:
                async with self.channel_layer.connection(0) as conn:
                    online = int(await conn.hget(f"exam:{self.exam.id}:{s}", "sessions") or 0)
                    students.append({
                        'student': s,
                        'sessions': online,
                        'answers': self.exam.get_answers(s),
                        "uploads": self.exam.get_uploads(s),
                    })

            await self.accept()

            init['all_questions'] = self.exam.get_questions()
            init['role'] = 'teacher'
            init['students'] = students

            await self.send_json(init)
            await self.channel_layer.group_add(exam_bcast_teacher_group(self.exam), self.channel_name)
        else:
            if self.scope['user'].username not in self.exam.students:
                logger.error(f"{self.scope['user'].username} not on exam!")
                return

            headers = self.scope['headers']
            useragent = ""
            ip = ""
            for k, v in headers:
                if k == b"user-agent":
                    useragent = v.decode('utf-8')
                elif k == b"x-real-ip":
                    ip = v.decode('utf-8')

            await self.log('connect', {
                "ip": ip,
                "useragent": useragent,
            })

            await self.increment_sessions(1)
            if question:
                init['answer'] = self.exam.get_student_answer(self.scope['user'].username, question['current_question'])

            init['role'] = 'student';
            if init['state'] == 'finished':
                init['my_answers'] = self.exam.get_answers(self.scope['user'].username) 
                init["uploads"] = self.exam.get_uploads(self.scope['user'].username)

            await self.accept()
            await self.send_json(init)
        await self.channel_layer.group_add(exam_bcast_group(self.exam), self.channel_name)

    async def disconnect(self, close_code):
        if not self.is_teacher:
            await self.log('disconnect')
            await self.increment_sessions(-1)

    async def send_current_question(self):
        question = await current_question(self.channel_layer, self.exam)
        if question is not None:
            await self.send_json(question)

    async def question(self, event):
        event['action'] = 'question'
        event['state'] = 'running'
        await self.send_json(event)

    async def log_send(self, event):
        await self.send_json(event)

    async def change_state(self, event):
        await self.send_json({
            'mutation': 'change_state',
            'state': event['state'],
        })

        if not self.is_teacher:
            await self.send_json({
                'mutation': 'init',
                'my_answers': self.exam.get_answers(self.scope['user'].username)
            })

    # handling input
    @allow_teacher
    async def receive_start(self, content):
        async with self.channel_layer.connection(0) as conn:
            conn.hdel(key(self.exam), "pause")

        await self.channel_layer.send('heartbeat', {
            'type': 'next_question',
            'exam_id': self.exam.id,
        })

    @allow_teacher
    async def receive_pause(self, content):
        async with self.channel_layer.connection(0) as conn:
            conn.hset(key(self.exam), "pause", 1)

        await self.channel_layer.send('heartbeat', {
            'type': 'pause',
            'exam_id': self.exam.id,
        })

        await self.channel_layer.group_send(exam_bcast_group(self.exam), {
            'type': 'change_state',
            'state': 'paused',
        })

    @allow_teacher
    async def receive_save_points(self, content):
        print(content)
        self.exam.save_points(content['student'], content.get('question'), content.get('points', ''), content.get('note', ''))

    async def receive_upload(self, content):
        self.exam.save_upload(self.scope['user'].username, content['filename'], base64.b64decode(content['data']))

        await self.send_json({
            'mutation': 'init',
            'uploads': self.exam.get_uploads(self.scope['user'].username)
        })

    async def receive_keydown(self, content):
        async with self.channel_layer.connection(0) as conn:
            content['question'] = int(await conn.hget(key(self.exam), 'idx'))
        await self.log('answer', content)
        self.exam.save_answer(self.scope['user'].username, content['question'], content['answer'])

    async def receive_log(self, content):
        await self.log(content['event'], content)

    async def receive_json(self, content):
        action = content['action']
        await getattr(self, f'receive_{action}')(content)


import sys
if sys.argv[1:] == ["runworker", "heartbeat"]:
    from django_rq.queues import get_connection
    redis = get_connection()
    for k in redis.keys("exam:*"):
        k = k.decode('utf-8')
        if k.count(':') == 1:
            logger.info(f"Pausing exam {k}")
            redis.hset(k, "pause", 1)
