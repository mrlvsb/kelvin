<script lang="ts" setup>
import CopyToClipboard from '../components/CopyToClipboard.vue';
import FullscreenImage from '../components/FullscreenImage.vue';
import SubmitSource from '../components/submit/SubmitSource.vue';
import { Comment, SourceFile, CommentCounts, SelectedRows } from '../types/TaskDetail';

const props = defineProps<{
  files: SourceFile[];
  commentCountsByPath: Record<string, CommentCounts>;
  selectedRows: SelectedRows | null;
  collapsable: boolean;
}>();

const emit = defineEmits<{
  'set-notification': [payload: { comment_id: number; unread: boolean }];
  'save-comment': [
    payload: {
      id?: number;
      text: string;
      success?: () => void;
      line?: number;
      source?: string;
      type?: string;
    }
  ];
  'resolve-suggestion': [payload: { id: number; comment: Comment }];
}>();

const collapseFile = (file: SourceFile) => {
  if (props.collapsable) {
    file.opened = !file.opened;
  }
};

const handleSaveComment = (
  source: string,
  payload: {
    id?: number;
    text: string;
    success?: () => void;
    line?: number;
    type?: string;
  }
) => {
  emit('save-comment', { ...payload, source });
};
</script>

<template>
  <div class="task-detail-content">
    <template v-for="file in props.files" :key="file.source.path">
      <h2 class="file-header">
        <span
          :class="{ 'file-header-clickable': props.collapsable }"
          :title="props.collapsable ? 'Toggle file visibility' : undefined"
          @click="collapseFile(file)"
        >
          <span>{{ file.source.path }}</span>

          <template v-if="file.source.comments && Object.keys(file.source.comments).length">
            <span class="comment-badges">
              <template v-if="props.commentCountsByPath[file.source.path]?.user > 0">
                <span class="badge bg-secondary" title="Student/teacher comments">
                  {{ props.commentCountsByPath[file.source.path].user }}
                </span>
              </template>

              <template v-if="props.commentCountsByPath[file.source.path]?.automated > 0">
                <span class="badge bg-primary" title="Automation comments">
                  {{ props.commentCountsByPath[file.source.path].automated }}
                </span>
              </template>
            </span>
          </template>
        </span>

        <CopyToClipboard
          v-if="file.source.type === 'source' && file.source.content"
          :content="() => file.source.content"
          title="Copy the source code to the clipboard"
        >
          <span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px" />
        </CopyToClipboard>

        <a
          class="text-body"
          :href="file.source.content_url || file.source.src"
          download
          title="Download the file"
        >
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
              props.selectedRows && props.selectedRows.path === file.source.path
                ? props.selectedRows
                : null
            "
            @set-notification="(payload) => emit('set-notification', payload)"
            @save-comment="(payload) => handleSaveComment(file.source.path, payload)"
            @resolve-suggestion="(payload) => emit('resolve-suggestion', payload)"
          />
        </template>

        <FullscreenImage
          v-else-if="file.source.type === 'img'"
          :src="file.source.src"
          alt="Image preview"
        />

        <video v-else-if="file.source.type === 'video'" style="max-width: 100%" controls>
          <source v-for="src in file.source.sources" :key="src" :src="src" />
        </video>

        <template v-else>The preview cannot be shown.</template>
      </template>
    </template>
  </div>
</template>

<style scoped>
.task-detail-content {
  flex: 1;
  min-width: 0;
  overflow: auto;
  width: 100%;
}

.file-header-clickable {
  cursor: pointer;
}

.file-header-clickable:hover {
  text-decoration: underline;
}

.file-header span .badge:hover {
  text-decoration: none;
}

.comment-badges {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 6px;
}

.comment-badges .badge {
  font-size: 0.6em;
  padding: 5px 10px;
  line-height: 1;
}
</style>
