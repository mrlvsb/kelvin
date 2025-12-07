<script setup lang="ts">
/**
 * Displays two inputs used to select date range.
 * User can make a selection using:
 *  - calendar widget
 *  - or by adding time from drop-down list to current value
 */

import { onMounted, watch, defineModel, ref } from 'vue';
import flatpickr from 'flatpickr';

let {
  timeOffsetInWeek,
  semesterBeginDate,
  onFromDuplicateClick,
  onToDuplicateClick,
  onToRelativeClick
} = defineProps<{
  timeOffsetInWeek: number;
  semesterBeginDate: Date;
  onFromDuplicateClick: (date: Date) => void;
  onToDuplicateClick: (date: Date) => void;
  onToRelativeClick: (assigned: Date, deadline: Date) => void;
}>();

/**
 * @model
 *
 * bound two variables with begin and end date
 *
 * @example
 *  v-model:from-date="assigned"
 *  v-model:to-date="deadline"
 */
const fromDate = defineModel<Date>('fromDate');
const toDate = defineModel<Date>('toDate');

const fromEl = ref<HTMLInputElement | null>(null);
const toEl = ref<HTMLInputElement | null>(null);
let instanceFrom: flatpickr.Instance, instanceTo: flatpickr.Instance;

onMounted(() => {
  if (fromEl.value && toEl.value) {
    const opts = {
      enableTime: true,
      time_24hr: true,
      altFormat: 'd. m. Y H:i',
      altInput: true
    };

    instanceFrom = flatpickr(fromEl.value, opts);
    instanceTo = flatpickr(toEl.value, opts);

    setDatePickers();
  }
});

function weekDate(n: number): Date {
  let date = new Date(semesterBeginDate.getTime());
  date.setDate(date.getDate() + 7 * n);
  date.setSeconds(timeOffsetInWeek);
  return date;
}

function weekStart(n: number): Date {
  let date = new Date(semesterBeginDate.getTime());
  date.setDate(date.getDate() + 7 * n);
  return date;
}

function addDeadline(minutes: number): void {
  if (!fromDate.value) {
    fromDate.value = new Date();
  }

  let date = new Date(fromDate.value);
  date.setMinutes(date.getMinutes() + minutes);
  toDate.value = date;
}

function setDatePickers() {
  if (instanceFrom) {
    instanceTo.set('minDate', fromDate.value);
    instanceFrom.setDate(fromDate.value);
  }

  if (instanceTo) {
    instanceTo.setDate(toDate.value);
    if (!fromDate.value) instanceTo._input.setAttribute('disabled', 'disabled');
    else if (instanceTo._input.hasAttribute('disabled'))
      instanceTo._input.removeAttribute('disabled');
  }
}

//enable disable second input based on first one value
watch([fromDate, toDate], setDatePickers);
</script>

<template>
  <div class="col">
    <div class="input-group input-group-sm">
      <button
        class="btn btn-primary dropdown-toggle"
        data-bs-toggle="dropdown"
        type="button"
        aria-expanded="false"
      ></button>
      <ul class="dropdown-menu">
        <button class="dropdown-item" @click="fromDate = new Date()">Now</button>
        <button v-for="i in 14" :key="i" class="dropdown-item" @click="fromDate = weekDate(i)">
          Week {{ i + 1 }}
          <span v-if="weekStart(i) <= new Date() && new Date() <= weekStart(i + 1)">
            <span class="iconify" data-icon="akar-icons:arrow-back"></span>
          </span>
        </button>
      </ul>
      <input ref="fromEl" v-model="fromDate" class="form-control" placeholder="Assigned" />
      <button
        class="btn btn-sm btn-secondary"
        title="Set assigned date to all visible classes"
        :disabled="!fromDate"
        @click.prevent="onFromDuplicateClick(fromDate)"
      >
        <span class="iconify" data-icon="mdi:content-duplicate"></span>
      </button>
    </div>
  </div>

  <div class="col">
    <div class="input-group input-group-sm">
      <button
        class="btn btn-primary dropdown-toggle"
        data-bs-toggle="dropdown"
        type="button"
        aria-expanded="false"
        :disabled="!fromDate"
      ></button>
      <ul class="dropdown-menu">
        <button class="dropdown-item" @click="addDeadline(1 * 45)">+ 1×45 min</button>
        <button class="dropdown-item" @click="addDeadline(30)">+ 30 min</button>
        <button class="dropdown-item" @click="addDeadline(2 * 45)">+ 2×45 min</button>
        <button class="dropdown-item" @click="addDeadline(3 * 45)">+ 3×45 min</button>
        <button class="dropdown-item" @click="addDeadline(1 * 60)">+ 1×60 min</button>
        <button class="dropdown-item" @click="addDeadline(2 * 60)">+ 2×60 min</button>
        <button class="dropdown-item" @click="addDeadline(3 * 60)">+ 3×60 min</button>
        <button class="dropdown-item" @click="addDeadline(60 * 24 * 7)">+ week</button>
      </ul>
      <input ref="toEl" v-model="toDate" class="form-control" placeholder="Deadline" />
      <button
        class="btn btn-sm btn-secondary"
        title="Set deadline to all assigned classes"
        :disabled="!toDate"
        @click.prevent="onToDuplicateClick(toDate)"
      >
        <span class="iconify" data-icon="mdi:content-duplicate"></span>
      </button>
      <button
        class="btn btn-sm btn-secondary"
        title="Set relative deadline to all assigned classes"
        :disabled="!toDate"
        @click.prevent="onToRelativeClick(fromDate, toDate)"
      >
        <span class="iconify" data-icon="mdi:calendar-sync"></span>
      </button>
    </div>
  </div>
</template>
