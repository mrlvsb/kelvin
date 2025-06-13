<script setup lang="ts">
/**
 * This component displays a table that shows quiz submits.
 * It is only available for teachers.
 */
import { onMounted, ref } from 'vue';
import type { Config, ConfigColumns, Api as DataTableObject } from 'datatables.net';
import DataTablesCore from 'datatables.net-bs5';
import DataTable from 'datatables.net-vue3';
import { format } from 'date-fns';
import { getFromAPI } from '../../utilities/api';

DataTable.use(DataTablesCore);

const { quiz_id } = defineProps<{
  quiz_id: number;
}>();

type Submit = {
  id: number;
  classId: number;
  className: string;
  student: string;
  score: number;
  scoringLink: string;
  date: Date;
};

type SortValue = 'asc' | 'desc';
type OrderColumn = 'created_at';

/**
 * Get submits from API
 * @param classId Class id
 * @param count Count of records
 * @param start Offset of records
 * @param sortCol Column to sort by
 * @param sort Type of sorting
 * @param search Search query
 * @returns Tuple of [total count, quizzes]
 */
const getSubmits = async (
  classId: string,
  count: number,
  start = 0,
  sortCol: OrderColumn,
  sort: SortValue = 'desc',
  search: string = ''
): Promise<[number, Submit[]]> => {
  const params = new URLSearchParams();

  let classPath = '';
  if (classId !== 'all') {
    classPath = `/${classId}`;
  }

  params.append('count', count.toString());
  params.append('start', start.toString());
  params.append('sort', sort);
  params.append('search', search);
  params.append('order_column', sortCol);

  const data = await getFromAPI<{
    submits: Submit[];
    count: number;
  }>(`/api/quiz/${quiz_id}/submits${classPath}?${params.toString()}`);

  if (data) {
    return [
      data.count,
      data.submits.map((submit) => {
        return {
          ...submit,
          //parse date, and since django returns the correct format we can just pass it to the Date constructor
          date: new Date(submit.date)
        } satisfies Submit;
      })
    ];
  }

  return [0, []];
};

type Class = {
  classId: number;
  className: string;
};

const classes = ref(Array<Class>());

/**
 * Get scoped classes from server by quiz id
 */
const getClasses = async () => {
  const data = await getFromAPI<{
    classes: Class[];
  }>(`/api/quiz/${quiz_id}/classes`);

  if (data) {
    classes.value = data.classes;
  }
};

await getClasses();

let classId = ref('all');

const columns = [
  {
    title: 'Id',
    data: 'id',
    searchable: false,
    orderable: false,
    visible: false
  },
  {
    title: 'Class',
    data: 'className',
    orderable: false,
    searchable: false
  },
  {
    title: 'Student',
    data: 'student',
    orderable: false,
    searchable: false
  },
  {
    title: 'Scoring',
    data: (row: Submit) => row,
    orderable: false,
    searchable: false,
    render: (data: Submit) => `<a href="${data.scoringLink}" target="_blank">Edit scoring</a>`
  },
  {
    title: 'Score',
    data: 'score',
    orderable: false,
    searchable: false
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
    callback: (data: { data: Submit[]; recordsTotal: number; recordsFiltered: number }) => void
  ) => {
    let col = data.order.find((order) => order.column === 5);
    let orderColumn: OrderColumn = 'created_at';

    const [count, items] = await getSubmits(
      classId.value,
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

const onChangeClass = () => {
  //invalidate cells to load data again with
  table.draw();
};
</script>

<template>
  <div class="d-flex gap-1 justify-content-start">
    <select v-model="classId" class="form-select" @change="onChangeClass">
      <option value="all" selected>All</option>
      <option v-for="clazz in classes" :key="clazz.classId" :value="clazz.classId">
        {{ clazz.className }}
      </option>
    </select>
  </div>

  <DataTable ref="dataTable" class="table table-striped" :columns="columns" :options="options">
  </DataTable>
</template>

<style>
@import 'datatables.net-bs5';
</style>
