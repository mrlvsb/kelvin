<script lang="ts" setup>
import { computed, onUnmounted, ref } from 'vue';
import type { SourceFile, CommentCounts } from '../types/TaskDetail';

type FileTreeEntry = {
  name: string;
  path: string | null;
  depth: number;
  isFile: boolean;
  commentCounts?: CommentCounts;
};

type FileTreeNode = {
  name: string;
  path: string | null;
  children: Map<string, FileTreeNode>;
  isFile: boolean;
  commentCounts?: CommentCounts;
};

const props = defineProps<{
  files: SourceFile[];
  commentCountsByPath: Record<string, CommentCounts>;
  selectedPath: string | null;
}>();

const emit = defineEmits<{
  select: [path: string];
}>();

const sidebarRef = ref<HTMLElement | null>(null);

let isDragging = false;
let dragStartX = 0;
let dragStartWidth = 0;

const minWidth = 250;
const width = ref<number>(250);
const maxWidth = 400;

const fileTreeEntries = computed<FileTreeEntry[]>(() => {
  if (!props.files.length) {
    return [];
  }

  const root: FileTreeNode = {
    name: '',
    path: null,
    children: new Map(),
    isFile: false
  };

  for (const file of props.files) {
    const parts = file.source.path.split('/');
    let current = root;

    parts.forEach((part: string, index: number) => {
      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          path: null,
          children: new Map(),
          isFile: false
        });
      }

      const nextNode = current.children.get(part);
      if (!nextNode) {
        return;
      }

      current = nextNode;

      if (index === parts.length - 1) {
        current.path = file.source.path;
        current.isFile = true;
        current.commentCounts = props.commentCountsByPath[file.source.path];
      }
    });
  }

  const entries: FileTreeEntry[] = [];

  const walk = (node: FileTreeNode, depth: number) => {
    const children = Array.from(node.children.values()).sort((a, b) => {
      if (a.isFile !== b.isFile) {
        return a.isFile ? 1 : -1;
      }
      return a.name.localeCompare(b.name);
    });

    for (const child of children) {
      entries.push({
        name: child.name,
        path: child.path,
        depth,
        isFile: child.isFile,
        commentCounts: child.commentCounts
      });

      if (child.children.size > 0) {
        walk(child, depth + 1);
      }
    }
  };

  walk(root, 0);
  return entries;
});

const handleSelect = (path: string | null) => {
  if (!path) {
    return;
  }

  emit('select', path);
};

const clampWidth = (value: number) => {
  return Math.min(Math.max(value, minWidth), maxWidth);
};

const handlePointerMove = (event: PointerEvent) => {
  if (!isDragging) {
    return;
  }

  width.value = clampWidth(dragStartWidth + (event.clientX - dragStartX));
};

const stopDragging = () => {
  if (!isDragging) {
    return;
  }

  isDragging = false;
  document.body.style.userSelect = '';
  window.removeEventListener('pointermove', handlePointerMove);
  window.removeEventListener('pointerup', stopDragging);
};

const startDragging = (event: PointerEvent) => {
  if (event.button !== 0) {
    return;
  }

  isDragging = true;
  dragStartX = event.clientX;
  dragStartWidth = sidebarRef.value?.offsetWidth ?? width.value;

  document.body.style.userSelect = 'none';
  window.addEventListener('pointermove', handlePointerMove);
  window.addEventListener('pointerup', stopDragging);
};

onUnmounted(() => {
  stopDragging();
});
</script>

<template>
  <aside
    ref="sidebarRef"
    class="task-detail-sidebar"
    :style="{
      width: `${width}px`,
      maxWidth: `${maxWidth}px`
    }"
  >
    <ul class="file-tree">
      <li
        v-for="(entry, entryIndex) in fileTreeEntries"
        :key="entry.path ? entry.path : `${entry.name}-${entry.depth}-${entryIndex}`"
        :style="{ '--tree-depth': entry.depth }"
      >
        <button
          v-if="entry.isFile"
          class="file-tree__item"
          :class="{ 'file-tree__item--active': entry.path === props.selectedPath }"
          @click="handleSelect(entry.path)"
        >
          <span class="iconify" data-icon="fontisto:file-1"></span>

          <span class="file-tree__label" :title="entry.name">{{ entry.name }}</span>

          <span
            v-if="entry.commentCounts?.user || entry.commentCounts?.automated"
            class="comment-badges"
          >
            <span
              v-if="entry.commentCounts?.user"
              class="badge bg-secondary"
              title="Student/teacher comments"
            >
              {{ entry.commentCounts.user }}
            </span>

            <span
              v-if="entry.commentCounts?.automated"
              class="badge bg-primary"
              title="Automation comments"
            >
              {{ entry.commentCounts.automated }}
            </span>
          </span>
        </button>

        <div v-else class="file-tree__folder">
          <span class="iconify" data-icon="fa-solid:folder"></span>
          <span class="file-tree__label" :title="entry.name">{{ entry.name }}</span>
        </div>
      </li>
    </ul>

    <div class="task-detail-sidebar__splitter" @pointerdown="startDragging"></div>
  </aside>
</template>

<style scoped>
.task-detail-sidebar {
  flex: 0 0 auto;
  overflow: hidden;
  border-right: 1px solid #dee2e6;
  padding-right: 12px;
  position: relative;
  min-width: 180px;
}

.file-tree {
  list-style: none;
  margin: 0;
  padding: 0;
}

.file-tree li {
  margin-bottom: 4px;
}

.file-tree__item,
.file-tree__folder {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 4px 6px;
  padding-left: calc(var(--tree-depth) * 16px + 6px);
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  font-size: 0.9rem;
}

.file-tree__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.comment-badges {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 6px;
}

.comment-badges .badge {
  font-size: 0.6em;
  padding: 4px 6px;
  line-height: 1;
}

.file-tree__item {
  cursor: pointer;
  border-radius: 4px;
}

:global(html[data-bs-theme='dark'] .file-tree__item:hover, .file-tree__item--active) {
  background-color: #ffffff17;
}

:global(html[data-bs-theme='dark'] .file-tree__item--active) {
  background-color: #ffffff25;
}

:global(html[data-bs-theme='light'] .file-tree__item:hover, .file-tree__item--active) {
  background-color: #0000000d;
}

:global(html[data-bs-theme='light'] .file-tree__item--active) {
  background-color: #0000001a;
}

.task-detail-sidebar__splitter {
  position: absolute;
  top: 0;
  right: -6px;
  width: 12px;
  height: 100%;
  cursor: col-resize;
}
</style>
