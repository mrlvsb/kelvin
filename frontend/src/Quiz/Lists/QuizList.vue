<script setup lang="ts">
/**
 * This component displays a table that allows filtering and sorting of quizzes. It is also possible to add a quiz.
 * It is only available for teachers.
 */
import { onMounted, reactive, ref } from 'vue';
import type { Config, ConfigColumns, Api as DataTableObject } from 'datatables.net';
import DataTablesCore from 'datatables.net-bs5';
import DataTable from 'datatables.net-vue3';
import { format } from 'date-fns';
import Modal from 'bootstrap/js/dist/modal';
import { getDataWithCSRF, getFromAPI } from '../../utilities/api';

DataTable.use(DataTablesCore);

type Quiz = {
  id: string;
  date: Date;
  name: string;
  editLink: string;
  submitsLink: string;
};

type SortValue = 'asc' | 'desc';
type OrderColumn = 'created_at' | 'name';

/**
 * Get quizzes from API
 * @param subject Subject abbreviation
 * @param count Count of records
 * @param start Offset of records
 * @param sortCol Column to sort by
 * @param sort Type of sorting
 * @param search Search query
 * @returns Tuple of [total count, quizzes]
 */
const getQuizzes = async (
  subject: string,
  count: number,
  start = 0,
  sortCol: OrderColumn,
  sort: SortValue = 'desc',
  search: string = ''
): Promise<[number, Quiz[]]> => {
  const params = new URLSearchParams();

  let subjectPath = '';
  if (subject !== 'all') {
    subjectPath = `/${subject}`;
  }

  params.append('count', count.toString());
  params.append('start', start.toString());
  params.append('sort', sort);
  params.append('search', search);
  params.append('order_column', sortCol);

  const data = await getFromAPI<{
    quizzes: Quiz[];
    count: number;
  }>(`/api/quiz-list${subjectPath}?${params.toString()}`);

  if (data) {
    return [
      data.count,
      data.quizzes.map((quiz) => {
        return {
          ...quiz,
          //parse date, and since django returns the correct format we can just pass it to the Date constructor
          date: new Date(quiz.date)
        } satisfies Quiz;
      })
    ];
  }

  return [0, []];
};

type Subject = {
  abbr: string;
  name: string;
};

const subjects = ref(Array<Subject>());

const quizAddModalState = reactive({
  quiz_add_modal: null
});

const selectedSubjectAbbr = ref<string>('');
const selectedName = ref<string>('');

/**
 * Open quiz add modal
 */
const openQuizAddModal = () => {
  quizAddModalState.quiz_add_modal.show();
};

/**
 * Close quiz add modal
 */
const closeQuizAddModal = () => {
  quizAddModalState.quiz_add_modal.hide();
};

const addQuiz = async () => {
  const data = await getDataWithCSRF<{ message: string }>('/api/quiz/add', 'POST', {
    subject: selectedSubjectAbbr.value,
    name: selectedName.value
  });

  if (data && data.message) {
    closeQuizAddModal();
    table.draw();
  }
};

/**
 * Get subjects from server
 */
const getSubjects = async () => {
  const data = await getFromAPI<{
    subjects: Subject[];
  }>('/api/subjects/all');

  if (data) {
    subjects.value = data.subjects;

    if (data.subjects.length > 0) selectedSubjectAbbr.value = data.subjects[0].abbr;
  }
};

await getSubjects();

let subject = ref('all');

const columns = [
  {
    title: 'Id',
    data: 'id',
    searchable: false,
    orderable: false,
    visible: false
  },
  {
    title: 'Name',
    data: (row: Quiz) => row,
    orderable: true,
    searchable: true,
    render: (data: Quiz) => `<a href="${data.editLink}">${data.name}</a>`
  },
  {
    title: 'Subject',
    data: 'subject',
    orderable: false,
    searchable: false
  },
  {
    title: 'Submits',
    data: (row: Quiz) => row,
    orderable: false,
    searchable: false,
    render: (data: Quiz) => `<a href="${data.submitsLink}">Show submits</a>`
  },
  {
    title: 'Created At',
    data: 'date',
    orderable: true,
    searchable: false,
    render: (data: Date) => format(data, 'yyyy-MM-dd hh:mm')
  }
] satisfies ConfigColumns[];

const options = {
  stripeClasses: ['table-striped', 'table-hover'],
  serverSide: true,
  ajax: async (
    data: {
      length: number;
      start: number;
      order: {
        column: number;
        dir: SortValue;
        name: string;
      }[];
      search: {
        value: string;
      };
    },
    callback: (data: { data: Quiz[]; recordsTotal: number; recordsFiltered: number }) => void
  ) => {
    let col = data.order.find((order) => order.column === 4);
    let orderColumn: OrderColumn = 'created_at';
    if (!col) {
      col = data.order.find((order) => order.column === 1);
      if (col) orderColumn = 'name';
    }

    const [count, items] = await getQuizzes(
      subject.value,
      data.length,
      data.start,
      orderColumn,
      col?.dir ?? 'desc',
      data.search.value
    );

    callback({ data: items, recordsTotal: count, recordsFiltered: count }); // https://datatables.net/manual/server-side#Returned-data
  },
  orderMulti: false,
  pageLength: 25
} satisfies Config;

//save ref to data table and if it changes save datatable instance to table variable
const dataTable = ref();
let table: DataTableObject<unknown>;

onMounted(() => {
  quizAddModalState.quiz_add_modal = new Modal('#quiz_add_modal', {});
  table = dataTable.value?.dt;
});

const filterChanged = () => {
  //invalidate cells to load data again with
  table.draw();
};
</script>

<template>
  <div class="d-flex justify-content-end">
    <button class="btn btn-primary mb-2" @click="openQuizAddModal">Add quiz</button>
  </div>
  <div class="d-flex gap-1 justify-content-start">
    <label for="subject-select" class="mt-2 form-label">Subject: </label>
    <select id="subject-select" v-model="subject" class="form-select" @change="filterChanged">
      <option value="all" selected>All</option>
      <option v-for="subj in subjects" :key="subj.abbr" :value="subj.abbr">
        {{ subj.name }}
      </option>
    </select>
  </div>

  <DataTable ref="dataTable" class="table table-striped" :columns="columns" :options="options">
  </DataTable>
  <div
    class="modal fade"
    id="quiz_add_modal"
    tabindex="-1"
    aria-labelledby="quiz_add_modal_label"
    aria-hidden="true"
  >
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="quiz_add_modal_label">Add quiz</h5>
          <button
            type="button"
            class="btn-close"
            aria-label="Close"
            @click="closeQuizAddModal"
          ></button>
        </div>
        <div class="modal-body row justify-content-center">
          <div class="col-12 mb-1">
            <label for="subject-select" class="form-label">Subject</label>
            <select id="subject-select" class="form-control" v-model="selectedSubjectAbbr">
              <option :value="subject.abbr" v-for="subject in subjects" :key="subject.abbr">
                {{ subject.name }}
              </option>
            </select>
          </div>
          <div class="col-12 mb-1">
            <label for="name-select" class="form-label">Name</label>
            <input id="name-select" class="form-control" type="text" v-model="selectedName" />
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-primary" @click="addQuiz">Add quiz</button>
          <button type="button" class="btn btn-secondary" @click="closeQuizAddModal">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
@import 'datatables.net-bs5';
</style>
