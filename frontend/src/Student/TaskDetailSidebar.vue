<script lang="ts" setup>
import { computed, onUnmounted, ref, watch, defineExpose } from 'vue';
import type { SourceFile, CommentCounts } from '../types/TaskDetail';

type FileTreeEntry = {
  name: string;
  path: string | null;
  folderPath?: string | null;
  depth: number;
  isFile: boolean;
  isCollapsed?: boolean;
  commentCounts?: CommentCounts;
};

type FileTreeNode = {
  name: string;
  path: string | null;
  folderPath: string | null;
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

const collapsedByPath = ref<Record<string, boolean>>({});

const collectFolderPaths = (sourceFiles: SourceFile[]) => {
  const folders = new Set<string>();

  for (const file of sourceFiles) {
    const parts = file.source.path.split('/');
    let currentPath = '';

    for (let index = 0; index < parts.length - 1; index += 1) {
      currentPath = currentPath ? `${currentPath}/${parts[index]}` : parts[index];
      folders.add(currentPath);
    }
  }

  return folders;
};

const isFolderCollapsed = (folderPath: string | null | undefined) => {
  if (!folderPath) {
    return false;
  }

  return collapsedByPath.value[folderPath] ?? false;
};

const allFoldersOpen = computed(() => {
  const folderPaths = collectFolderPaths(props.files);
  if (!folderPaths.size) {
    return true;
  }

  for (const folderPath of folderPaths) {
    if (collapsedByPath.value[folderPath]) {
      return false;
    }
  }

  return true;
});

watch(
  () => props.files,
  (nextFiles, previousFiles) => {
    const folderPaths = collectFolderPaths(nextFiles);
    const previousFolderPaths = previousFiles
      ? collectFolderPaths(previousFiles)
      : new Set<string>();

    // First load: collapse all folders by default
    if (!previousFiles?.length) {
      const nextCollapsedByPath: Record<string, boolean> = {};
      for (const folderPath of folderPaths) {
        nextCollapsedByPath[folderPath] = true;
      }
      collapsedByPath.value = nextCollapsedByPath;
      return;
    }

    // Preserve existing collapse state, collapse newly added folders, drop removed folders
    const nextCollapsedByPath: Record<string, boolean> = { ...collapsedByPath.value };

    // Newly added folders start collapsed
    for (const folderPath of folderPaths) {
      if (!previousFolderPaths.has(folderPath) && nextCollapsedByPath[folderPath] !== true) {
        nextCollapsedByPath[folderPath] = true;
      }
    }

    // Remove folders that no longer exist
    for (const key of Object.keys(nextCollapsedByPath)) {
      if (!folderPaths.has(key)) {
        delete nextCollapsedByPath[key];
      }
    }

    collapsedByPath.value = nextCollapsedByPath;
  },
  { immediate: true }
);

const fileTreeEntries = computed<FileTreeEntry[]>(() => {
  if (!props.files.length) {
    return [];
  }

  const root: FileTreeNode = {
    name: '',
    path: null,
    folderPath: null,
    children: new Map<string, FileTreeNode>(),
    isFile: false
  };

  for (const file of props.files) {
    const parts = file.source.path.split('/');
    let current = root;
    let currentPath = '';

    parts.forEach((part: string, index: number) => {
      if (!current.children.has(part)) {
        const nextPath = currentPath ? `${currentPath}/${part}` : part;
        current.children.set(part, {
          name: part,
          path: null,
          folderPath: nextPath,
          children: new Map<string, FileTreeNode>(),
          isFile: false
        });
      }

      const nextNode = current.children.get(part);
      if (!nextNode) {
        return;
      }

      current = nextNode;
      currentPath = current.folderPath ?? currentPath;

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
      const folderPath: string | null = child.folderPath;

      entries.push({
        name: child.name,
        path: child.path,
        folderPath,
        depth,
        isFile: child.isFile,
        isCollapsed: child.isFile ? undefined : isFolderCollapsed(folderPath),
        commentCounts: child.commentCounts
      });

      if (child.children.size > 0 && !isFolderCollapsed(folderPath)) {
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

const toggleFolder = (folderPath: string | null | undefined) => {
  if (!folderPath) {
    return;
  }

  collapsedByPath.value = {
    ...collapsedByPath.value,
    [folderPath]: !(collapsedByPath.value[folderPath] ?? false)
  };
};

const toggleAllFolders = () => {
  const folderPaths = collectFolderPaths(props.files);
  if (!folderPaths.size) {
    return;
  }

  const nextCollapsedState = allFoldersOpen.value;
  const nextCollapsedByPath: Record<string, boolean> = { ...collapsedByPath.value };

  for (const folderPath of folderPaths) {
    nextCollapsedByPath[folderPath] = nextCollapsedState;
  }

  collapsedByPath.value = nextCollapsedByPath;
};

const handlePointerMove = (event: PointerEvent) => {
  if (!isDragging) {
    return;
  }

  const calculatedWidth = dragStartWidth + (event.clientX - dragStartX);
  width.value = Math.min(Math.max(calculatedWidth, minWidth), maxWidth);
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

const expandParentsForPath = (selectedPath: string) => {
  const pathParts = selectedPath.split('/');
  if (pathParts.length <= 1) {
    return;
  }

  const nextCollapsedByPath: Record<string, boolean> = { ...collapsedByPath.value };
  let currentFolderPath = '';

  for (let index = 0; index < pathParts.length - 1; index += 1) {
    currentFolderPath = currentFolderPath
      ? `${currentFolderPath}/${pathParts[index]}`
      : pathParts[index];

    nextCollapsedByPath[currentFolderPath] = false;
  }

  collapsedByPath.value = nextCollapsedByPath;
};

watch(
  () => props.selectedPath,
  (nextSelectedPath) => {
    if (!nextSelectedPath) {
      return;
    }
    expandParentsForPath(nextSelectedPath);
  },
  { immediate: true }
);

onUnmounted(() => {
  stopDragging();
});

defineExpose({
  allFoldersOpen,
  toggleAllFolders
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
          <span class="iconify" data-icon="fa7-solid:file-alt"></span>

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

        <button
          v-else
          class="file-tree__folder"
          type="button"
          @click="toggleFolder(entry.folderPath)"
        >
          <span class="file-tree__toggle">
            <span v-show="entry.isCollapsed">
              <span class="iconify" data-icon="fa7-solid:folder"></span>
            </span>

            <span v-show="!entry.isCollapsed">
              <span class="iconify" data-icon="fa7-solid:folder-open"></span>
            </span>
          </span>

          <span class="file-tree__label" :title="entry.name">{{ entry.name }}</span>
        </button>
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
  padding: 4px 6px 4px calc(var(--tree-depth) * 15px + 5px);
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  font-size: 0.9rem;
}

.file-tree__toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  height: 12px;
  color: inherit;
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

.file-tree__folder {
  cursor: pointer;
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
