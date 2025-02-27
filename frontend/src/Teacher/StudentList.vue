<script setup lang="ts">
/**
 * This component displays a table that allows searching students.
 * It is only available to teachers, and it is accessible from the main page.
 */
import { Config, ConfigColumns, AjaxData } from 'datatables.net';
import DataTablesCore from 'datatables.net-bs5';
import DataTable from 'datatables.net-vue3';
import { getFromAPI } from '../utilities/api';

DataTable.use(DataTablesCore);

type Student = {
  login: string;
  name: string;
};

/**
 * Get students from API
 * @param count Count of records
 * @param start Offset of records
 * @param search Search query
 * @returns Tuple of [total count, students]
 */
const getStudents = async (
  count: number,
  start = 0,
  search: string = ''
): Promise<[number, Student[]]> => {
  const params = new URLSearchParams();

  params.append('count', count.toString());
  params.append('start', start.toString());
  params.append('search', search);

  const data = await getFromAPI<{
    students: Student[];
    count: number;
  }>(`/api/student-list?${params.toString()}`);
  if (data) {
    return [data.count, data.students];
  }

  return [0, []];
};

const columns: ConfigColumns[] = [
  {
    title: 'Login',
    data: 'login',
    orderable: false,
    searchable: true
  },
  {
    title: 'Name',
    data: 'name',
    orderable: false,
    searchable: true
  }
];

const options: Config = {
  stripeClasses: ['table-striped', 'table-hover'],
  serverSide: true,
  ajax: async (
    data: AjaxData,
    callback: (data: { data: Student[]; recordsTotal: number; recordsFiltered: number }) => void
  ) => {
    const [count, items] = await getStudents(data.length, data.start, data.search.value);

    callback({ data: items, recordsTotal: count, recordsFiltered: count });
  },
  pageLength: 25,
  layout: {
    topStart: 'search',
    topEnd: 'pageLength'
  }
} satisfies Config;
</script>

<template>
  <DataTable class="table table-striped" :columns="columns" :options="options" />
</template>

<style>
@import 'datatables.net-bs5';
</style>
