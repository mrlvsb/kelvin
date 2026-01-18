<script lang="ts" setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import SyncLoader from '../components/SyncLoader.vue';
import SummaryComments from '../components/submit/SummaryComments.vue';
import SubmitsDiff from '../components/submit/SubmitsDiff.vue';
import TaskDetailSidebar from './TaskDetailSidebar.vue';
import TaskDetailContent from './TaskDetailContent.vue';
import { fetch } from '../api';
import { user } from '../global';
import { markRead } from '../utilities/notifications';
import { hideComments, viewMode, HideCommentsState, ViewModeState } from '../stores';
import { useSvelteStore } from '../utilities/useSvelteStore';
import { Comment, SelectedRows, Source, Submit } from '../types/TaskDetail';

const props = defineProps<{
  url: string;
  comment_url: string;
}>();

const files = ref<SourceFile[] | null>(null);
const summaryComments = ref<Comment[]>([]);
const submits = ref<Submit[] | null>(null);
const current_submit = ref<number | null>(null);
const deadline = ref<number | string | null>(null);
const showDiff = ref(false);
const selectedRows = ref<SelectedRows | null>(null);
const selectedFilePath = ref<string | null>(null);

const currentUser = useSvelteStore(user, null);
const hideCommentsValue = useSvelteStore(hideComments, HideCommentsState.NONE);
const viewModeValue = useSvelteStore(viewMode, ViewModeState.LIST);

const commentsButton = {
  [HideCommentsState.NONE]: {
    title: 'Click to hide automated comments',
    icon: 'fa-solid:comment'
  },
  [HideCommentsState.AUTOMATED]: {
    title: 'Click to hide all comments',
    icon: 'fa-solid:comment-medical'
  },
  [HideCommentsState.ALL]: {
    title: 'Click to show all comments',
    icon: 'fa-solid:comment-slash'
  }
};

const viewModeButton = {
  [ViewModeState.LIST]: {
    title: 'Switch to tree view',
    icon: 'fa7-solid:folder-tree'
  },
  [ViewModeState.TREE]: {
    title: 'Switch to list view',
    icon: 'fa-solid:list'
  }
};

const commentsUI = computed(() => commentsButton[hideCommentsValue.value]);
const viewModeUI = computed(() => viewModeButton[viewModeValue.value]);

const downloadHref = computed(() => {
  if (typeof window === 'undefined') {
    return '';
  }

  return `kelvin:${window.location.href.split('#')[0]}download`;
});

class SourceFile {
  source: Source;
  opened: boolean;

  constructor(source: Source) {
    this.source = source;
    this.opened = true;
  }
}

const changeCommentState = () => {
  let nextState = HideCommentsState.NONE;

  switch (hideCommentsValue.value) {
    case HideCommentsState.NONE:
      nextState = HideCommentsState.AUTOMATED;
      break;
    case HideCommentsState.AUTOMATED:
      nextState = HideCommentsState.ALL;
      break;
    case HideCommentsState.ALL:
      nextState = HideCommentsState.NONE;
      break;
  }

  hideComments.set(nextState);
};

const changeViewMode = () => {
  let nextMode = ViewModeState.LIST;

  switch (viewModeValue.value) {
    case ViewModeState.LIST:
      nextMode = ViewModeState.TREE;
      break;
    case ViewModeState.TREE:
      nextMode = ViewModeState.LIST;
      break;
  }

  viewMode.set(nextMode);
};

const updateCommentProps = (id: number, newProps: Partial<Comment> | null) => {
  const update = (items: Comment[]) => {
    return items
      .map((comment) => {
        if (comment.id == id) {
          if (newProps === null) {
            return null;
          }

          return { ...comment, ...newProps };
        }

        return comment;
      })
      .filter((comment) => comment !== null);
  };

  files.value = files.value.map((file) => {
    if (file.source.comments) {
      file.source.comments = Object.fromEntries(
        Object.entries(file.source.comments).map(([lineNum, comments]) => {
          return [lineNum, update(comments)];
        })
      );
    }

    return file;
  });

  summaryComments.value = update(summaryComments.value);
};

const markCommentAsRead = async (comment: Comment) => {
  if (
    comment.unread &&
    currentUser.value &&
    comment.author_id !== currentUser.value.id &&
    comment.notification_id
  ) {
    await markRead(comment.notification_id);
    comment.unread = false;
  }

  return comment;
};

type CommentSavePayload = {
  id?: number;
  text: string;
  success?: () => void;
  line?: number;
  source?: string;
  type?: string;
};

const addNewComment = async (comment: CommentSavePayload) => {
  const { success, ...payload } = comment;

  const res = await fetch(props.comment_url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  const json = await res.json();
  if (res.ok) success();

  if (!comment.source) {
    summaryComments.value = [
      ...(await Promise.all(summaryComments.value.map(markCommentAsRead))),
      json
    ];
  } else {
    files.value = await Promise.all(
      files.value.map(async (file) => {
        if (file.source.path === comment.source) {
          let comments = await Promise.all(
            (file.source.comments[comment.line - 1] || []).map(markCommentAsRead)
          );

          file.source.comments[comment.line - 1] = [...comments, json];
        }

        return file;
      })
    );
  }
};

const updateComment = async (id: number, text: string) => {
  await fetch(`${props.comment_url}/${id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      text
    })
  });

  updateCommentProps(id, text === '' ? null : { text });
};

const saveComment = async (comment: CommentSavePayload) => {
  if (comment.id) {
    await updateComment(comment.id, comment.text);
  } else {
    await addNewComment(comment);
  }

  if (comment.success) {
    comment.success();
  }
};

const setNotification = async (evt: { comment_id: number; unread: boolean }) => {
  const walk = async (comments: Comment[]) => {
    if (comments.filter((comment) => comment.id === evt.comment_id).length) {
      for (const comment of comments) {
        if (
          comment.unread &&
          currentUser.value &&
          comment.author_id !== currentUser.value.id &&
          comment.notification_id
        ) {
          await markRead(comment.notification_id);
          updateCommentProps(comment.id, { unread: evt.unread });
        }
      }
    }
  };

  await walk(summaryComments.value);
  for (const source of files.value) {
    if (source.source.comments) {
      for (const comments of Object.values(source.source.comments)) {
        await walk(comments);
      }
    }
  }
};

const resolveSuggestion = (evt: { id: number; comment: Comment | null }) => {
  const comment = evt.comment;

  summaryComments.value = summaryComments.value.filter(
    (existing) => existing.meta?.review?.id !== evt.id
  );

  files.value = files.value.map((file) => {
    if (!file.source.comments) {
      return file;
    }

    const updated = { ...file.source.comments };
    Object.keys(updated).forEach((line) => {
      updated[line] = updated[line].filter((existing) => existing.meta?.review?.id !== evt.id);
    });

    return {
      ...file,
      source: {
        ...file.source,
        comments: updated
      }
    };
  });

  if (!comment) {
    return;
  }

  if (comment.line === null || comment.line === undefined) {
    summaryComments.value = [...summaryComments.value, comment];
    return;
  }

  files.value = files.value.map((file) => {
    if (file.source.path === comment.source) {
      const lineIndex = comment.line - 1;
      const comments = file.source.comments?.[lineIndex] || [];

      return {
        ...file,
        source: {
          ...file.source,
          comments: {
            ...file.source.comments,
            [lineIndex]: [...comments, comment]
          }
        }
      };
    }

    return file;
  });
};

const keydown = (event: KeyboardEvent) => {
  const targetElement = event.target as HTMLElement | null;

  if (
    targetElement?.getAttribute('contenteditable') ||
    targetElement?.tagName === 'TEXTAREA' ||
    targetElement?.tagName === 'INPUT'
  ) {
    return;
  }

  let targetSubmit = null;
  if (event.key === 'ArrowLeft' && current_submit.value > 1) {
    if (event.shiftKey) {
      targetSubmit = 1;
    } else {
      targetSubmit = current_submit.value - 1;
    }
  } else if (
    event.key === 'ArrowRight' &&
    submits.value &&
    current_submit.value < submits.value.length
  ) {
    if (event.shiftKey) {
      targetSubmit = submits.value.length;
    } else {
      targetSubmit = current_submit.value + 1;
    }
  }

  if (targetSubmit !== null) {
    document.location.href = `../${targetSubmit}${document.location.hash}`;
  }
};

const countComments = (comments: Record<string, Comment[]> | undefined) => {
  comments = comments || {};

  const counts = {
    user: 0,
    automated: 0
  };

  for (const line of Object.values(comments)) {
    for (const comment of Object.values(line)) {
      if (comment.type === 'automated' || comment.type === 'ai-review') {
        counts.automated += 1;
      } else {
        counts.user += 1;
      }
    }
  }

  return counts;
};

const commentCountsByPath = computed(() => {
  if (!files.value) {
    return {};
  }

  return Object.fromEntries(
    files.value.map((file) => [file.source.path, countComments(file.source.comments)])
  );
});

const allOpen = computed(() => {
  return (
    files.value &&
    files.value.reduce((sum, file) => sum + (file.opened ? 1 : 0), 0) === files.value.length
  );
});

const visibleFiles = computed(() => {
  if (!files.value) {
    return [];
  }

  if (viewModeValue.value === ViewModeState.TREE) {
    if (!selectedFilePath.value) {
      return [];
    }

    return files.value.filter((file) => file.source.path === selectedFilePath.value);
  }

  return files.value;
});

const toggleOpen = () => {
  if (!files.value) {
    return;
  }

  const areAllOpened = allOpen.value;
  const nextOpenedState = !areAllOpened;

  files.value = files.value.map((file) => {
    return {
      ...file,
      opened: nextOpenedState
    };
  });
};

const setSelectedFile = (path: string | null, updatePath: boolean = false) => {
  if (!path || !files.value) {
    return;
  }

  selectedFilePath.value = path;
  const file = files.value.find((item) => item.source.path === path);

  if (file) {
    file.opened = true;

    if (updatePath) {
      document.location.hash = `#src;${path}`;
    }
  }
};

const getLineElement = (path: string, line: number) => {
  return document.querySelector(
    `table[data-path="${CSS.escape(path)}"] .linecode[data-line="${CSS.escape(String(line))}"]`
  );
};

function isLineVisible(path: string, line: number): boolean {
  const lineElement: HTMLElement | null = getLineElement(path, line) as HTMLElement | null;
  if (!lineElement) {
    return false;
  }

  // Check if line element is within the viewport
  const rect = lineElement.getBoundingClientRect();
  return (
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  );
}

const updateSelectedFileAndRows = (): SelectedRows => {
  const s = document.location.hash.split(';', 2);
  let selected: SelectedRows = null;

  if (s.length === 2) {
    const parts = s[1].split(':');

    if (parts.length === 1) {
      const targetPath = parts[0];

      selected = {
        path: targetPath,
        from: 0,
        to: 0
      };
    } else if (parts.length === 2) {
      const range = parts[1].split('-');
      const targetPath = parts[0];

      selected = {
        path: targetPath,
        from: parseInt(range[0]),
        to: parseInt(range[1] || range[0])
      };
    }
  }

  selectedRows.value = selected;
  return selected;
};

const scrollToSelection = () => {
  const selection = selectedRows.value;
  if (!selection) {
    return;
  }

  const { path, from: line } = selection;

  setTimeout(() => {
    if (isLineVisible(path, line)) {
      return;
    }

    const el = getLineElement(path, line) as HTMLElement | null;
    if (el) el.scrollIntoView();
  }, 0);
};

const findFirstFileIndex = () => {
  if (!files.value) {
    return -1;
  }

  // Firstly, try to locate README file
  const readmeRegex = /^readme(\.md|\.txt)?$/i;
  const readmeIndex = files.value.findIndex((file) => readmeRegex.test(file.source.path));

  // Default to first file if no README found
  if (readmeIndex === -1) {
    return 0;
  }

  return readmeIndex;
};

const load = async () => {
  const res = await fetch(props.url);
  const json = await res.json();

  current_submit.value = json.current_submit;
  deadline.value = json.deadline;
  submits.value = json.submits;
  files.value = json.sources.map((source) => new SourceFile(source));
  summaryComments.value = json.summary_comments;

  if (files.value.length > 1) {
    for (const file of files.value) {
      file.opened = false;
    }
  }

  // If only one file, switch to list view
  if (files.value.length <= 1) {
    viewMode.set(ViewModeState.LIST);
  } else {
    viewMode.set(ViewModeState.TREE);
  }

  const selectedFile = updateSelectedFileAndRows();

  if (selectedFile) {
    setSelectedFile(selectedFile.path);
    scrollToSelection();
  } else {
    const firstFileIndex = findFirstFileIndex();

    if (firstFileIndex !== -1) {
      setSelectedFile(files.value[firstFileIndex].source.path);
    }
  }
};

onMounted(() => {
  load();
  window.addEventListener('keydown', keydown);
  window.addEventListener('hashchange', updateSelectedFileAndRows);
});

onUnmounted(() => {
  window.removeEventListener('keydown', keydown);
  window.removeEventListener('hashchange', updateSelectedFileAndRows);
});

watch([files, viewModeUI], () => {
  if (viewModeUI.value !== 'tree') {
    return;
  }

  if (!files.value || files.value.length === 0) {
    return;
  }

  const hasSelection =
    selectedFilePath.value &&
    files.value.some((file) => file.source.path === selectedFilePath.value);

  if (!hasSelection) {
    const firstFileIndex = findFirstFileIndex();

    if (firstFileIndex !== -1) {
      setSelectedFile(files.value[firstFileIndex].source.path);
    }
  }
});
</script>

<template>
  <div v-if="files === null" class="d-flex justify-content-center">
    <SyncLoader />
  </div>

  <div v-else>
    <div class="float-end d-flex gap-1">
      <button
        v-if="files.length > 1 && viewMode === 'list'"
        class="btn btn-link p-0"
        title="Expand or collapse all files"
        @click="toggleOpen"
      >
        <span v-if="allOpen">
          <span class="iconify" data-icon="ant-design:folder-open-filled"></span>
        </span>

        <span v-else>
          <span class="iconify" data-icon="ant-design:folder-filled"></span>
        </span>
      </button>

      <button class="btn p-0 btn-link" :title="viewModeUI.title" @click="changeViewMode">
        <div :key="viewModeUI.icon">
          <span class="iconify" :data-icon="viewModeUI.icon"></span>
        </div>
      </button>

      <button class="btn p-0 btn-link" :title="commentsUI.title" @click="changeCommentState">
        <div :key="commentsUI.icon">
          <span class="iconify" :data-icon="commentsUI.icon"></span>
        </div>
      </button>

      <button
        class="btn p-0 btn-link"
        title="Diff vs previous version(s)"
        @click="showDiff = !showDiff"
      >
        <span class="iconify" data-icon="fa-solid:history"></span>
      </button>

      <a :href="downloadHref" title="Open on your PC">
        <span class="iconify" data-icon="fa-solid:external-link-alt"></span>
      </a>

      <a href="download" download title="Download">
        <span class="iconify" data-icon="fa-solid:download"></span>
      </a>
    </div>

    <SubmitsDiff
      v-if="showDiff"
      :submits="submits"
      :current_submit="current_submit"
      :deadline="deadline"
    />

    <SummaryComments
      :summary-comments="summaryComments"
      @save-comment="saveComment"
      @set-notification="setNotification"
      @resolve-suggestion="resolveSuggestion"
    />

    <div :class="['task-detail-body', { 'task-detail-tree-body': viewModeValue === 'tree' }]">
      <TaskDetailSidebar
        v-if="viewModeValue === 'tree'"
        :files="files || []"
        :comment-counts-by-path="commentCountsByPath"
        :selected-path="selectedFilePath"
        @select="(path) => setSelectedFile(path, true)"
      />

      <TaskDetailContent
        :files="visibleFiles"
        :comment-counts-by-path="commentCountsByPath"
        :selected-rows="selectedRows"
        @set-notification="setNotification"
        @save-comment="saveComment"
        @resolve-suggestion="resolveSuggestion"
      />
    </div>
  </div>
</template>

<style scoped>
video,
img {
  max-width: 100%;
}

.task-detail-body {
  width: 100%;
}

.task-detail-tree-body {
  display: flex;
  gap: 16px;
  overflow: hidden;
}
</style>
