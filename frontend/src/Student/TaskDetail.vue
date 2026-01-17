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
import { hideComments, HideCommentsState } from '../stores';
import { useSvelteStore } from '../utilities/useSvelteStore';
import { localStorageStore } from '../utilities/storage';
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

// View mode is defaulted to 'auto', which switches between 'list' and 'tree' based on number of files
// Soon as user changes the view mode, it is stored in local storage to persist across sessions
export type ViewMode = 'auto' | 'list' | 'tree';
const storedViewMode = localStorageStore<ViewMode>('view-mode', 'auto');
const viewMode = ref<ViewMode>(storedViewMode.value);

const currentUser = useSvelteStore(user, null);
const hideCommentsValue = useSvelteStore(hideComments, HideCommentsState.NONE);

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

const commentsUI = computed(() => commentsButton[hideCommentsValue.value]);
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

const detectViewMode = () => {
  // Force list view if there is only one file
  if (files.value.length <= 1) {
    return 'list';
  }

  if (storedViewMode.value === 'auto') {
    if (files.value.length > 1) {
      return 'tree';
    } else {
      return 'list';
    }
  }

  return storedViewMode.value;
};

const visibleFiles = computed(() => {
  if (!files.value) {
    return [];
  }

  if (viewMode.value === 'tree') {
    if (!selectedFilePath.value) {
      return [];
    }

    return files.value.filter((file) => file.source.path === selectedFilePath.value);
  }

  return files.value;
});

const toggleOpen = () => {
  const nextOpenedState = !allOpen.value;

  files.value = files.value.map((file) => {
    return {
      ...file,
      opened: nextOpenedState
    };
  });
};

const toggleViewMode = () => {
  if (!viewMode.value || viewMode.value === 'list') {
    viewMode.value = 'tree';
  } else {
    viewMode.value = 'list';
  }

  // Store the user's preference
  storedViewMode.value = viewMode.value;
};

const setSelectedFilePath = (path: string | null, options?: { openFile?: boolean }) => {
  if (!path) {
    return;
  }

  selectedFilePath.value = path;

  if (options?.openFile) {
    const file = files.value?.find((item) => item.source.path === path);
    if (file) {
      file.opened = true;
    }
  }
};

const goToSelectedLines = () => {
  const s = document.location.hash.split(';', 2);

  if (s.length === 2) {
    const parts = s[1].split(':');

    if (parts.length === 2) {
      const range = parts[1].split('-');
      const targetPath = parts[0];

      selectedRows.value = {
        path: targetPath,
        from: parseInt(range[0]),
        to: parseInt(range[1] || range[0])
      };

      setSelectedFilePath(targetPath, { openFile: true });

      setTimeout(() => {
        const el = document.querySelector(
          `table[data-path="${CSS.escape(targetPath)}"] .linecode[data-line="${CSS.escape(String(selectedRows.value.from))}"]`
        );

        if (el) {
          el.scrollIntoView();
        }
      }, 0);

      return parts[0];
    }
  }

  return null;
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

  viewMode.value = detectViewMode();
  const selectedFile = goToSelectedLines();

  if (selectedFile !== null) {
    setSelectedFilePath(selectedFile, { openFile: true });
  }
};

onMounted(() => {
  load();
  window.addEventListener('keydown', keydown);
  window.addEventListener('hashchange', goToSelectedLines);
});

onUnmounted(() => {
  window.removeEventListener('keydown', keydown);
  window.removeEventListener('hashchange', goToSelectedLines);
});

watch([files, viewMode], () => {
  if (viewMode.value !== 'tree') {
    return;
  }

  if (!files.value || files.value.length === 0) {
    return;
  }

  const hasSelection =
    selectedFilePath.value &&
    files.value.some((file) => file.source.path === selectedFilePath.value);

  if (!hasSelection) {
    setSelectedFilePath(files.value[0].source.path, { openFile: true });
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

      <button
        v-if="files.length > 1"
        class="btn btn-link p-0"
        title="Switch between list and tree view"
        @click="toggleViewMode"
      >
        <span v-if="viewMode === 'tree'">
          <span class="iconify" data-icon="fa7-solid:folder-tree"></span>
        </span>

        <span v-else>
          <span class="iconify" data-icon="fa-solid:list"></span>
        </span>
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

    <div :class="['task-detail-body', { 'task-detail-tree-body': viewMode === 'tree' }]">
      <TaskDetailSidebar
        v-if="viewMode === 'tree'"
        :files="files || []"
        :comment-counts-by-path="commentCountsByPath"
        :selected-path="selectedFilePath"
        @select="(path) => setSelectedFilePath(path, { openFile: true })"
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
