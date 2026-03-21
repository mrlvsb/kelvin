<script setup lang="ts">
import { onMounted, ref, computed, type ComputedRef } from 'vue';
import { fetch } from '../../api';
import { clickOutside } from '../../utilities/clickOutside';

interface Room {
  id: number;
  code: string;
}

interface ViewRoom extends Room {
  isSelected: boolean;
}

let { onDuplicateClick, disabled = false } = defineProps<{
  onDuplicateClick: (selected: number[]) => void;
  disabled: boolean;
}>();

const selectedRooms = defineModel<number[]>({
  required: false
});

let allRooms = ref<Room[]>(null);

const vClickOutside = clickOutside;

onMounted(async () => {
  const req = await fetch('/api/classrooms-list/');
  allRooms.value = await req.json();

  if (selectedRooms.value == undefined) selectedRooms.value = [];
});

const allRoomsList: ComputedRef<ViewRoom[]> = computed(() => {
  if (!allRooms.value) return [];

  return allRooms.value.map((room) => {
    return {
      ...room,
      isSelected: selectedRooms.value.includes(room.id)
    };
  });
});

let search = ref<string>('');
let showDropdown = ref<boolean>(false);

function toggleItem(item: ViewRoom) {
  item.isSelected = !item.isSelected;

  if (item.isSelected) {
    selectedRooms.value.push(item.id);
  } else {
    const idx = selectedRooms.value.indexOf(item.id);
    if (idx > -1) {
      selectedRooms.value.splice(idx, 1);
    }
  }
}

const sortedClassroomList: ComputedRef<ViewRoom[]> = computed(() => {
  return allRoomsList.value
    .filter((i) => i.code.toLowerCase().includes(search.value.toLowerCase()))
    .sort((a, b) => {
      if (a.isSelected && !b.isSelected) return -1;
      if (!a.isSelected && b.isSelected) return 1;

      return a.code.localeCompare(b.code);
    });
});

const selectedCount: ComputedRef<number> = computed(
  () => allRoomsList.value.filter((i) => i.isSelected).length
);
</script>

<template>
  <div v-click-outside="() => (showDropdown = false)" class="dropdown" style="position: relative">
    <div class="input-group">
      <input
        type="button"
        :value="selectedCount > 0 ? `${selectedCount} classroom(s) selected` : 'Select classrooms'"
        :disabled="disabled"
        class="btn btn-sm btn-primary"
        @click="showDropdown = !showDropdown"
      />
      <button
        class="btn btn-sm btn-secondary"
        title="Set assigned classroom list to all visible classes"
        :disabled="disabled"
        @click.prevent="() => onDuplicateClick(selectedRooms)"
      >
        <span class="iconify" data-icon="mdi:content-duplicate"></span>
      </button>
    </div>

    <div
      v-if="showDropdown"
      class="card p-3 mt-2"
      style="position: absolute; z-index: 1000; width: 250px; max-height: 200px; overflow-y: auto"
    >
      <input v-model="search" type="text" placeholder="Search..." class="form-control mb-2" />

      <div v-for="room in sortedClassroomList" :key="room.id" class="form-check">
        <input
          :id="'classroom' + room.id"
          :checked="room.isSelected"
          type="checkbox"
          class="form-check-input"
          @change="() => toggleItem(room)"
        />
        <label class="form-check-label" :for="'classroom' + room.id">{{ room.code }}</label>
      </div>

      <small v-if="selectedCount === 0" class="text-black">No classrooms found</small>
    </div>
  </div>
</template>

<style scoped>
.dropdown .card {
  background: white;
  border: 1px solid #ddd;
  border-radius: 0.25rem;
  color: black;
}
</style>
