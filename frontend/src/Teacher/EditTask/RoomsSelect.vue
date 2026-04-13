<script setup lang="ts">
import { ref, computed, type ComputedRef } from 'vue';
import { clickOutside } from '../../utilities/clickOutside';
import { Room } from './RoomInterface';

interface ViewRoom extends Room {
  isSelected: boolean;
}

let {
  allRooms,
  onDuplicateClick,
  disabled = false
} = defineProps<{
  allRooms: Room[];
  onDuplicateClick: (selected: number[]) => void;
  disabled: boolean;
}>();

const selectedRooms = defineModel<number[]>({ default: () => [] });

const vClickOutside = clickOutside;

const allRoomsList: ComputedRef<ViewRoom[]> = computed(() => {
  if (!allRooms) return [];

  return allRooms.map((room) => {
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

      <small v-if="sortedClassroomList.length === 0" class="text-black">No classrooms found</small>
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
