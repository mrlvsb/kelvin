<script setup lang="ts">
/**
 * This component displays a table that allows filtering and sorting
 * of tasks.
 * It is only available to teachers, and it is accessible from the main page.
 */
import type { Config, ConfigColumns, Api as DataTableObject } from 'datatables.net';
import DataTablesCore from 'datatables.net-bs5';
import DataTable from 'datatables.net-vue3';
import { format } from 'date-fns';
import { onMounted, ref } from 'vue';
import { getFromAPI } from '../utilities/api';

DataTable.use(DataTablesCore);

type Task = {
  id: string;
  title: string;
  subject: string;
  date: Date;
  link: string;
};

type RawTask = Omit<Task, 'date'> & {
  date: string;
};

type SortValue = 'asc' | 'desc';
type OrderColumn = 'created_at' | 'name';

/**
 * Get tasks from API
 * @param subject Subject abbreviation
 * @param count Count of records
 * @param start Offset of records
 * @param sort Type of sorting
 * @param search Search query
 * @returns Tuple of [total count, tasks]
 */
const getTasks = async (
  subject: string,
  count: number,
  start = 0,
  sortCol: OrderColumn,
  sort: SortValue = 'desc',
  search: string = ''
): Promise<[number, Task[]]> => {
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
    tasks: RawTask[];
    count: number;
  }>(`/api/task-list${subjectPath}?${params.toString()}`);

  if (data) {
    return [
      data.count,
      data.tasks.map((task) => {
        return {
          ...task,
          //parse date, and since django returns the correct format we can just pass it to the Date constructor
          date: new Date(task.date)
        } satisfies Task;
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

const loaded = ref(false);
const getSubjects = async () => {
  const data = await getFromAPI<{
    subjects: Subject[];
  }>('/api/subjects/all');

  if (data) {
    subjects.value = data.subjects;
    loaded.value = true;
  }
};

await getSubjects();

const columns = [
  {
    title: 'Id',
    data: 'id',
    searchable: false,
    orderable: false,
    visible: false
  },
  {
    title: 'Title',
    data: (row: Task) => row,
    orderable: true,
    searchable: true,
    render: (data: Task) => `<a href="${data.link}" target="_blank">${data.title}</a>`
  },
  {
    title: 'Subject',
    data: 'subject',
    orderable: false,
    searchable: false
  },
  {
    title: 'Created At',
    data: 'date',
    orderable: true,
    searchable: false,
    render: (data: Date) => format(data, 'yyyy-MM-dd hh:mm')
  },
  {
    title: 'Moss check',
    orderable: false,
    searchable: false,
    render: '#moss',
    data: null,
    className: 'dt-body-right dt-head-right'
  }
] satisfies ConfigColumns[];

let subject = ref('all');

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
    callback: (data: { data: Task[]; recordsTotal: number; recordsFiltered: number }) => void
  ) => {
    let col = data.order.find((order) => order.column === 3);
    let orderColumn: OrderColumn = 'created_at';
    if (!col) {
      col = data.order.find((order) => order.column === 1);
      if (col) orderColumn = 'name';
    }

    const [count, items] = await getTasks(
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
  table = dataTable.value?.dt;
});

const onChangeSubject = () => {
  //invalidate cells to load data again with
  table.draw();
};
</script>

<template>
  <div class="d-flex gap-1 justify-content-start">
    <select v-model="subject" class="form-select" @change="onChangeSubject">
      <option value="all" selected>All</option>
      <option v-for="subj in subjects" :key="subj.abbr" :value="subj.abbr">
        {{ subj.name }}
      </option>
    </select>
  </div>

  <DataTable ref="dataTable" class="table table-striped" :columns="columns" :options="options">
    <template #moss="props">
      <a class="btn btn-secondary btn-sm" :href="`/teacher/task/${props.cellData.id}/plagcheck`">
        MOSS check
      </a>
    </template>
  </DataTable>
</template>

<style>
@import 'datatables.net-bs5';
</style>
