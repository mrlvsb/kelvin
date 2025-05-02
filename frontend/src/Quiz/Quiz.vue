<script setup lang="ts">
/**
 * This component displays a quiz that can "work" in 4 modes, based on passed parameters.
 * It is available for teachers and students.
 *
 * For teacher, it can act like a component to view detail of quiz, or to score quiz.
 * For student, it can act like a component to fill a quiz, or to view quiz results.
 */
import { ref, onMounted, onUnmounted } from 'vue';
import VueCountdown from '@chenfengyuan/vue-countdown';
import { getDataWithCSRF } from '../utilities/api';

type QuizData = {
  quiz_html: string;
  user: number;
  student: string;
  remaining: string;
  answers: string;
  scoring: string;
  quiz_id: number;
  is_teacher: boolean;
  enrolled_id: number;
  scored_by: string;
};

const props = defineProps<{
  quizData: QuizData;
}>();

enum Modes {
  Display,
  Filling,
  Scoring,
  ViewScoring
}

enum SubmitType {
  Periodic = 0,
  Manual = 1
}

const SENDING_INTERVAL_MS = 5000;
const answeredData =
  props.quizData.answers != null && (JSON.parse(props.quizData.answers) as AnswersData);
const scoringData =
  props.quizData.scoring != null && (JSON.parse(props.quizData.scoring) as ScoringData);
const isScoring = scoringData && Object.keys(scoringData).length !== 0;
const mode = props.quizData.is_teacher
  ? isScoring
    ? Modes.Scoring
    : Modes.Display
  : isScoring
    ? Modes.ViewScoring
    : Modes.Filling;
const quiz = ref<QuestionRender[]>(
  JSON.parse(props.quizData.quiz_html).map((q) => {
    q['unansweredAsterisk'] = mode === Modes.Filling;
    return q;
  }) satisfies QuestionRender[]
);
const currentQuestionIndex = ref<number>(0);
const answersRef = ref({});
const scoringPointsRef = ref({});
const scoringCommentsRef = ref({});
const scoringUnsaved = ref<boolean>(false);
const remainingTime = parseFloat(props.quizData.remaining) * 1000;
let sendingIntervalHandle = 0;
type IdentityHtml = {
  id: string;
  htmlContent: HTMLElement;
};
type QuestionRender = IdentityHtml & {
  name: string;
  type: QuestionType;
  points: number;
  answers?: IdentityHtml[];
  unansweredAsterisk: boolean;
};
type QuestionType = 'open' | 'abcd' | 'abcd.multiple';
type Answer = {
  id?: string;
  answer: string | boolean;
};
type Score = {
  points: number;
  comment: string;
};
type AnswersData = {
  [key: string]: Answer[];
};
type ScoringData = {
  [key: string]: Score;
};
/**
 * Collects answers from the quiz and returns them in a format that can be sent to the server.
 */
const collectAnswers = () => {
  const submit = {};
  for (const question of quiz.value) {
    submit[question.id] = [];
    if (question.type === 'open') {
      submit[question.id].push({ answer: answersRef.value[question.id].value });
    } else if (question.type === 'abcd' || question.type === 'abcd.multiple') {
      for (const answer of question.answers) {
        submit[question.id].push({ id: answer.id, answer: answersRef.value[answer.id].checked });
      }
    } else {
      console.error('Unknown question type');
    }
  }
  return { submit: submit };
};
/**
 * Selects a question to be displayed.
 * @param index Index of the question to be displayed.
 */
const selectQuestion = (index: number) => {
  currentQuestionIndex.value = index;
};
/**
 * Sends answers to the server.
 * @param answers_type If submit, the interval for sending answers will be cleared.
 */
const sendAnswers = async (answers_type: SubmitType) => {
  if (answers_type == SubmitType.Manual) {
    clearInterval(sendingIntervalHandle);
  }
  const answers = collectAnswers();
  const data = await getDataWithCSRF<{ redirect?: string }>(
    `/api/quiz/${props.quizData.enrolled_id}/result/${answers_type}`,
    'POST',
    answers
  );
  if (!data) {
    console.error('Error during saving results.');
    return;
  }
  if ('redirect' in data) {
    window.location.href = data.redirect;
    return;
  }
};
/**
 * Sends teacher scoring to the server.
 */
const sendScoring = async () => {
  if (!scoringUnsaved.value) {
    return;
  }
  const scoring = collectScoring();
  await getDataWithCSRF(`/api/quiz/${props.quizData.enrolled_id}/scoring`, 'POST', scoring);
  scoringUnsaved.value = false;
};
/**
 * Collects teacher scoring of the quiz.
 */
const collectScoring = () => {
  const scoring = {};
  for (const question_id of Object.keys(scoringData)) {
    scoring[question_id] = {
      points: parseFloat(scoringPointsRef.value[question_id].value) || 0,
      comment: scoringCommentsRef.value[question_id].value
    };
  }
  return { scoring: scoring };
};
/**
 * Opens dialog to submit the quiz.
 */
const submitQuiz = async () => {
  if (mode === Modes.Filling) {
    const submitMessage =
      'Are you sure you want to submit quiz?' +
      (quiz.value.some((q) => q.unansweredAsterisk) ? ' There are unanswered questions.' : '');
    if (confirm(submitMessage)) {
      await sendAnswers(SubmitType.Manual);
    }
  }
};
onMounted(() => {
  if (mode === Modes.Filling) {
    sendingIntervalHandle = setInterval(async () => {
      await sendAnswers(SubmitType.Periodic);
    }, SENDING_INTERVAL_MS);
  } else if (mode === Modes.Scoring) {
    sendingIntervalHandle = setInterval(sendScoring, SENDING_INTERVAL_MS);
  }
  for (const [question_id, answers] of Object.entries(answeredData)) {
    let isAnswered = false;
    for (const answer of answers) {
      if ('id' in answer) {
        answersRef.value[answer.id].checked = answer.answer;
        isAnswered = isAnswered || (answer.answer as boolean);
      } else {
        answersRef.value[question_id].value = answer.answer;
        isAnswered = (answer.answer as string) !== '';
      }
    }
    quiz.value.find((q) => q.id === question_id).unansweredAsterisk =
      mode === Modes.Filling && !isAnswered;
  }
});
onUnmounted(() => {
  if (mode === Modes.Scoring) {
    clearInterval(sendingIntervalHandle);
  }
});
</script>

<template>
  <div id="quiz">
    <div class="row">
      <div id="sidebar-wrapper" class="col-12 col-md-3 bg-light py-3">
        <vue-countdown
          v-if="mode === Modes.Filling"
          v-slot="{ hours, minutes, seconds }"
          :time="remainingTime"
          @end="sendAnswers(SubmitType.Manual)"
        >
          <div class="text-center mb-2">
            <strong>
              {{ hours.toString().padStart(2, '0') }}:{{ minutes.toString().padStart(2, '0') }}:{{
                seconds.toString().padStart(2, '0')
              }}
            </strong>
          </div>
        </vue-countdown>
        <template v-else-if="mode === Modes.ViewScoring">
          <h3 class="col-12 mb-4 text-center">
            <strong>Results summary:</strong>
          </h3>
          <h5 class="col-12 mb-2 text-center">
            <strong>Total:</strong>
            {{
              Object.values(scoringData).reduce((acc, val) => acc + parseFloat(val.points + ''), 0)
            }}
            points
          </h5>
          <h5 class="col-12 mb-4 text-center">
            <strong>Scored by:</strong>
            {{ props.quizData.scored_by || 'System Kelvin' }}
          </h5>
        </template>
        <h5 v-else-if="mode === Modes.Scoring" class="col-12 mb-2 text-center">
          <strong>Student:</strong>
          {{ props.quizData.student }}
        </h5>
        <ul class="list-unstyled">
          <li
            v-for="(question, index) in quiz"
            :key="question.id"
            :class="['py-2 text-center', { active: currentQuestionIndex === index }]"
            @click="selectQuestion(index)"
          >
            <span
              :class="[
                { 'text-primary': !question.unansweredAsterisk },
                { 'text-danger': question.unansweredAsterisk }
              ]"
              >Question {{ index + 1 }}</span
            >
            <span
              :style="{ display: question.unansweredAsterisk ? 'inline' : 'none' }"
              class="text-danger"
              title="Answer is empty."
              ><strong>*</strong></span
            >
          </li>
        </ul>
        <div class="text-center mt-2">
          <button
            v-if="!isScoring"
            class="btn btn-danger w-auto px-4"
            :disabled="props.quizData.is_teacher"
            @click="submitQuiz"
          >
            Submit
          </button>
          <button
            v-else-if="props.quizData.is_teacher"
            class="btn btn-success w-auto px-4"
            :disabled="!scoringUnsaved"
            @click="sendScoring"
          >
            Save scoring
          </button>
        </div>
      </div>
      <div id="page-content-wrapper" class="col-12 col-md-9 py-3">
        <div v-for="(question, index) in quiz" :key="question.id">
          <div v-show="currentQuestionIndex === index" class="question">
            <div class="card">
              <div class="card-header d-flex justify-content-between align-items-center">
                <h6>
                  <strong>Question {{ index + 1 }}</strong> / Points:
                  <strong>{{ question.points }}</strong>
                </h6>
                <input
                  v-if="mode === Modes.Scoring"
                  :ref="(el) => (scoringPointsRef[question.id] = el)"
                  type="number"
                  class="form-control float-end w-auto"
                  :value="scoringData[question.id].points"
                  min="0"
                  step="0.5"
                  @input="
                    scoringData[question.id].points =
                      parseFloat(scoringPointsRef[question.id].value) || 0;
                    scoringUnsaved = true;
                  "
                />
                <input
                  v-else-if="mode === Modes.ViewScoring"
                  :ref="(el) => (scoringPointsRef[question.id] = el)"
                  type="number"
                  class="form-control float-end w-auto teacher-scoring"
                  :value="scoringData[question.id].points"
                  disabled
                />
              </div>
              <div class="card-body">
                <template v-if="mode === Modes.Scoring">
                  <h6><strong>Comment:</strong></h6>
                  <textarea
                    v-if="mode === Modes.Scoring"
                    :ref="(el) => (scoringCommentsRef[question.id] = el)"
                    :value="scoringData[question.id].comment"
                    class="form-control mb-2 teacher-scoring"
                    rows="3"
                    placeholder="Add comment here"
                    @input="
                      scoringData[question.id].comment = scoringCommentsRef[question.id].value;
                      scoringUnsaved = true;
                    "
                  ></textarea>
                </template>
                <template
                  v-else-if="mode === Modes.ViewScoring && scoringData[question.id].comment"
                >
                  <h6><strong>Teacher's comment:</strong></h6>
                  <textarea
                    :ref="(el) => (scoringCommentsRef[question.id] = el)"
                    :value="scoringData[question.id].comment"
                    class="form-control mb-2 teacher-scoring"
                    rows="3"
                    disabled
                  ></textarea>
                </template>
                <h6 class="mt-2"><strong>Question:</strong></h6>
                <div v-html="question.htmlContent"></div>
                <h6 v-if="question.type === 'open' || question.type === 'abcd'" class="mt-2">
                  <strong>Answer:</strong>
                </h6>
                <h6 v-else class="mt-2"><strong>Answers:</strong></h6>
                <div v-if="question.type === 'open'" class="mt-3">
                  <textarea
                    v-if="!isScoring"
                    :ref="(el) => (answersRef[question.id] = el)"
                    class="form-control"
                    rows="3"
                    placeholder="Your answer"
                    @input="
                      question.unansweredAsterisk =
                        mode === Modes.Filling && answersRef[question.id].value === ''
                    "
                  ></textarea>
                  <textarea
                    v-else
                    :ref="(el) => (answersRef[question.id] = el)"
                    class="form-control"
                    rows="3"
                    disabled
                  ></textarea>
                </div>
                <div
                  v-else-if="question.type === 'abcd' || question.type === 'abcd.multiple'"
                  class="mt-3"
                >
                  <div
                    v-for="answer in question.answers"
                    :key="answer.id"
                    class="row border rounded mt-2 p-2"
                  >
                    <div class="col-11" v-html="answer.htmlContent"></div>
                    <div class="col-1 text-center align-self-center">
                      <input
                        v-if="!isScoring"
                        :ref="(el) => (answersRef[answer.id] = el)"
                        :type="question.type === 'abcd' ? 'radio' : 'checkbox'"
                        :name="'question-' + question.id"
                        class="form-check-input"
                        :value="answer.id"
                        @change="
                          question.unansweredAsterisk =
                            mode === Modes.Filling &&
                            question.answers.every((a) => !answersRef[a.id].checked)
                        "
                      />
                      <input
                        v-else
                        :ref="(el) => (answersRef[answer.id] = el)"
                        :type="question.type === 'abcd' ? 'radio' : 'checkbox'"
                        :name="'question-' + question.id"
                        class="form-check-input"
                        :value="answer.id"
                        disabled
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
#quiz:deep(#sidebar-wrapper) {
  height: 100%;
}

#quiz:deep(#sidebar-wrapper ul) {
  list-style: none;
  padding: 0;
  margin: 0;
}

#quiz:deep(#sidebar-wrapper li) {
  text-align: center;
  padding: 8px 0;
  cursor: pointer;
}

#quiz:deep(#sidebar-wrapper li:hover) {
  background-color: #e9ecef;
}

#quiz:deep(.active) {
  font-weight: bold;
  color: #007bff;
  background-color: #e9ecef;
  border-radius: 5px;
}

#quiz:deep(.card img) {
  height: auto;
  display: block;
  margin: 0 auto;
}

#quiz:deep(.teacher-scoring) {
  background-color: lightyellow;
}
</style>
