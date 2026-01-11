<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import SubmitSource from '../components/submit/SubmitSource.vue';
import SyncLoader from '../components/SyncLoader.vue';
import CopyToClipboard from '../components/CopyToClipboard.vue';
import SummaryComments from '../components/submit/SummaryComments.vue';
import SubmitsDiff from '../components/submit/SubmitsDiff.vue';
import { fetch } from '../api.js';
import { user } from '../global';
import { markRead } from '../utilities/notifications';
import { hideComments, HideCommentsState } from '../stores.js';
import { useSvelteStore } from '../utilities/useSvelteStore.js';

const props = defineProps({
  url: {
    type: String,
    required: true
  },
  comment_url: {
    type: String,
    required: true
  }
});

const files = ref(null);
const summaryComments = ref([]);
const submits = ref(null);
const current_submit = ref(null);
const deadline = ref(null);
const showDiff = ref(false);
const selectedRows = ref(null);

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
  constructor(source) {
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

const updateCommentProps = (id, newProps) => {
  const update = (items) => {
    return items
      .map((comment) => {
        if (comment.id === id) {
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

const markCommentAsRead = async (comment) => {
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

const addNewComment = async (comment) => {
  const res = await fetch(props.comment_url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(comment)
  });

  const json = await res.json();
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

const updateComment = async (id, text) => {
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

const saveComment = async (comment) => {
  if (comment.id) {
    await updateComment(comment.id, comment.text);
  } else {
    await addNewComment(comment);
  }

  if (comment.success) {
    comment.success();
  }
};

const setNotification = async (evt) => {
  const walk = async (comments) => {
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

const resolveSuggestion = (evt) => {
  const comment = evt.comment;

  if (comment.line === null || comment.line === undefined) {
    summaryComments.value = [...summaryComments.value, comment];
    return;
  }

  files.value = files.value.map((file) => {
    if (file.source.path === comment.source) {
      let comments = file.source.comments[comment.line - 1] || [];

      comments = comments.filter((c) => c.meta.review.id !== evt.id);

      file.source.comments[comment.line - 1] = [...comments, comment];
    }

    return file;
  });
};

const keydown = (event) => {
  if (
    event.target.getAttribute('contenteditable') ||
    event.target.tagName === 'TEXTAREA' ||
    event.target.tagName === 'INPUT'
  ) {
    return;
  }

  let target = null;
  if (event.key === 'ArrowLeft' && current_submit.value > 1) {
    if (event.shiftKey) {
      target = 1;
    } else {
      target = current_submit.value - 1;
    }
  } else if (
    event.key === 'ArrowRight' &&
    submits.value &&
    current_submit.value < submits.value.length
  ) {
    if (event.shiftKey) {
      target = submits.value.length;
    } else {
      target = current_submit.value + 1;
    }
  }
  if (target !== null) {
    document.location.href = `../${target}${document.location.hash}`;
  }
};

const countComments = (comments) => {
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

const allOpen = computed(() => {
  if (!files.value || files.value.length === 0) {
    return false;
  }

  return files.value.every((file) => file.opened === true);
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

const goToSelectedLines = () => {
  const s = document.location.hash.split(';', 2);

  if (s.length === 2) {
    const parts = s[1].split(':');

    if (parts.length === 2) {
      const range = parts[1].split('-');

      selectedRows.value = {
        path: parts[0],
        from: parseInt(range[0]),
        to: parseInt(range[1] || range[0])
      };

      setTimeout(() => {
        const el = document.querySelector(
          `table[data-path="${CSS.escape(parts[0])}"] .linecode[data-line="${CSS.escape(selectedRows.value.from)}"]`
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

  const selectedFile = goToSelectedLines();
  if (selectedFile !== null) {
    for (const file of files.value) {
      if (file.source.path === selectedFile) {
        file.opened = true;
      }
    }
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
</script>

<template>
  <div v-if="files === null" class="d-flex justify-content-center">
    <SyncLoader />
  </div>

  <div v-else>
    <div class="float-end">
      <button
        v-if="files.length > 1"
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

    <template v-for="file in files" :key="file.source.path">
      <h2 class="file-header">
        <span @click="file.opened = !file.opened">
          <span title="Toggle file visibility">{{ file.source.path }}</span>

          <template v-if="file.source.comments && Object.keys(file.source.comments).length">
            <template v-if="countComments(file.source.comments).user > 0">
              <span
                class="badge bg-secondary"
                title="Student/teacher comments"
                style="font-size: 60%"
              >
                {{ countComments(file.source.comments).user }}
              </span>
            </template>

            <template v-if="countComments(file.source.comments).automated > 0">
              <span class="badge bg-primary" title="Automation comments" style="font-size: 60%">
                {{ countComments(file.source.comments).automated }}
              </span>
            </template>
          </template>
        </span>

        <CopyToClipboard
          v-if="file.source.type === 'source' && file.source.content"
          :content="() => file.source.content"
          title="Copy the source code to the clipboard"
        >
          <span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px" />
        </CopyToClipboard>

        <!-- TODO: Fix download not working.. -->
        <a class="text-body" :href="file.source.content_url" download title="Download the file">
          <span class="iconify" data-icon="clarity:download-line" style="height: 20px" />
        </a>
      </h2>

      <template v-if="file.opened">
        <span v-if="file.source.error" class="text-muted">{{ file.source.error }}</span>
        <template v-else-if="file.source.type === 'source'">
          <template v-if="file.source.content === null">
            Content too large, show <a :href="file.source.content_url">raw content</a>.
          </template>

          <SubmitSource
            v-else
            :path="file.source.path"
            :code="file.source.content"
            :comments="file.source.comments"
            :selected-rows="
              selectedRows && selectedRows.path === file.source.path ? selectedRows : null
            "
            @set-notification="setNotification"
            @save-comment="(payload) => saveComment({ ...payload, source: file.source.path })"
            @resolve-suggestion="resolveSuggestion"
          />
        </template>

        <img v-else-if="file.source.type === 'img'" :src="file.source.src" />
        <video v-else-if="file.source.type === 'video'" controls>
          <source v-for="src in file.source.sources" :key="src" :src="src" />
        </video>

        <template v-else>The preview cannot be shown.</template>
      </template>
    </template>
  </div>
</template>

<style scoped>
video,
img {
  max-width: 100%;
}

.file-header span {
  cursor: pointer;
}

.file-header span:hover {
  text-decoration: underline;
}

.file-header span .badge:hover {
  text-decoration: none;
}
</style>
