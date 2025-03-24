<script setup lang="ts">
/**
 * This component displays a table that allows searching events for a given student.
 * It is only available to teachers.
 */
import { Config, ConfigColumns, AjaxData } from 'datatables.net';
import DataTablesCore from 'datatables.net-bs5';
import DataTable from 'datatables.net-vue3';
import { getFromAPI } from '../../utilities/api';
import { format } from 'date-fns';

DataTable.use(DataTablesCore);

const props = defineProps<{
  login: string;
}>();

type EventBase = {
  ip_address: string;
  created_at: string;
};

type LoginEvent = EventBase & {
  action: 'login';
};
type SubmitEvent = EventBase & {
  action: 'submit';
  metadata: {
    link: string;
    submit_num: number;
  };
};
type TaskDisplayedEvent = EventBase & {
  action: 'task-view';
  metadata: {
    link: string;
  };
};

type Event = LoginEvent | SubmitEvent | TaskDisplayedEvent;

const getEvents = async (
  login: string,
  count: number,
  start = 0,
  sortCol: string = 'created_at',
  sort: string = 'desc'
): Promise<[number, Event[]]> => {
  const params = new URLSearchParams();

  params.append('count', count.toString());
  params.append('start', start.toString());
  params.append('sort', sort);
  params.append('order_column', sortCol);

  const data = await getFromAPI<{
    events: Event[];
    count: number;
  }>(`/api/events/${login}?${params.toString()}`);
  if (data) {
    return [data.count, data.events];
  }

  return [0, []];
};

function formatAction(action: string): string {
  if (action === 'login') {
    return 'Login';
  } else if (action === 'submit') {
    return 'Submit';
  } else if (action === 'task-view') {
    return 'Assignment displayed';
  }
  return '<Unknown action>';
}

const columns: ConfigColumns[] = [
  {
    title: 'Action',
    name: 'action',
    data: 'action',
    render: (action: string) => formatAction(action)
  },
  {
    title: 'Link',
    name: 'link',
    data: (row: Event) => row,
    orderable: false
  },
  {
    title: 'IP address',
    name: 'ip_address',
    data: 'ip_address'
  },
  {
    title: 'Created At',
    name: 'created_at',
    data: 'created_at',
    render: (data: Date) => format(data, 'yyyy-MM-dd HH:mm')
  }
];

const options: Config = {
  stripeClasses: ['table-striped', 'table-hover'],
  serverSide: true,
  ajax: async (
    data: AjaxData,
    callback: (data: { data: Event[]; recordsTotal: number; recordsFiltered: number }) => void
  ) => {
    let sortColumn = 'created_at';
    let sortOrder = 'desc';
    if (data.order.length !== 0) {
      sortColumn = data.order[0]['name'];
      sortOrder = data.order[0].dir;
    }
    const [count, items] = await getEvents(
      props.login,
      data.length,
      data.start,
      sortColumn,
      sortOrder
    );

    callback({ data: items, recordsTotal: count, recordsFiltered: count });
  },
  pageLength: 50,
  layout: {
    topStart: null,
    topEnd: 'pageLength'
  }
} satisfies Config;
</script>

<template>
  <DataTable class="table table-striped" :columns="columns" :options="options">
    <template #column-link="props">
      <div v-if="props.rowData.action === 'submit'">
        <a :href="props.rowData.metadata.link" target="_blank">
          Submit #{{ props.rowData.metadata.submit_num }}
        </a>
      </div>
      <div v-if="props.rowData.action === 'task-view'">
        <a :href="props.rowData.metadata.link" target="_blank"> Task </a>
      </div>
    </template>
  </DataTable>
</template>

<style>
@import '../../../node_modules/datatables.net-bs5';
</style>
