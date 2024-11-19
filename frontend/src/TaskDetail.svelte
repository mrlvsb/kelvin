<script>
import SubmitSource from './SubmitSource.svelte';
import SyncLoader from './SyncLoader.svelte';
import CopyToClipboard from './CopyToClipboard.svelte';
import SummaryComments from './SummaryComments.svelte';
import SubmitsDiff from './SubmitsDiff.svelte';
import { fetch } from './api.js';
import { user } from './global';
import { notifications } from './utilities/notifications';
import { hideComments, HideCommentsState } from './stores.js';

export let url;
let files = null;
let summaryComments = [];
let submits = null;
let current_submit = null;
let deadline = null;
let showDiff = false;

const commentsButton = {
  [HideCommentsState.NONE]: { title: 'Click to hide automated comments', icon: 'fa-solid:comment' },
  [HideCommentsState.AUTOMATED]: {
    title: 'Click to hide all comments',
    icon: 'fa-solid:comment-medical'
  },
  [HideCommentsState.ALL]: { title: 'Click to show all comments', icon: 'fa-solid:comment-slash' }
};
let commentsUI = commentsButton[$hideComments];

function changeCommentState() {
  switch ($hideComments) {
    case HideCommentsState.NONE:
      $hideComments = HideCommentsState.AUTOMATED;
      break;
    case HideCommentsState.AUTOMATED:
      $hideComments = HideCommentsState.ALL;
      break;
    case HideCommentsState.ALL:
      $hideComments = HideCommentsState.NONE;
      break;
  }
  commentsUI = commentsButton[$hideComments];
}

class SourceFile {
  constructor(source) {
    this.source = source;
    this.opened = true;
  }
}

function updateCommentProps(id, newProps) {
  function update(items) {
    return items
      .map((c) => {
        if (c.id == id) {
          if (newProps === null) {
            return null;
          }
          return { ...c, ...newProps };
        }
        return c;
      })
      .filter((c) => c !== null);
  }

  files = files.map((file) => {
    if (file.source.comments) {
      file.source.comments = Object.fromEntries(
        Object.entries(file.source.comments).map(([lineNum, comments]) => {
          return [lineNum, update(comments)];
        })
      );
    }
    return file;
  });

  summaryComments = update(summaryComments);
}

async function addNewComment(comment) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(comment)
  });

  const json = await res.json();
  if (!comment.source) {
    summaryComments = [...(await Promise.all(summaryComments.map(markCommentAsRead))), json];
  } else {
    files = await Promise.all(
      files.map(async (file) => {
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
}

async function updateComment(id, text) {
  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      id: id,
      text: text
    })
  });

  updateCommentProps(id, text === '' ? null : { text });
}

async function saveComment(comment) {
  if (comment.id) {
    await updateComment(comment.id, comment.text);
  } else {
    await addNewComment(comment);
  }
  if (comment.success) {
    comment.success();
  }
}

async function markCommentAsRead(comment) {
  if (comment.unread && comment.author_id !== $user.id && comment.notification_id) {
    await notifications.markRead(comment.notification_id);
    comment.unread = false;
  }
  return comment;
}

async function setNotification(evt) {
  async function walk(comments) {
    if (comments.filter((c) => c.id === evt.detail.comment_id).length) {
      for (const comment of comments) {
        if (comment.unread && comment.author_id !== $user.id && comment.notification_id) {
          await notifications.markRead(comment.notification_id);
          updateCommentProps(comment.id, { unread: evt.detail.unread });
        }
      }
    }
  }

  await walk(summaryComments);
  for (const source of files) {
    if (source.source.comments) {
      for (const comments of Object.values(source.source.comments)) {
        await walk(comments);
      }
    }
  }
}

function keydown(e) {
  if (
    e.target.getAttribute('contenteditable') ||
    e.target.tagName === 'TEXTAREA' ||
    e.target.tagName == 'INPUT'
  ) {
    return;
  }

  let target = null;
  if (e.key === 'ArrowLeft' && current_submit > 1) {
    if (e.shiftKey) {
      target = 1;
    } else {
      target = current_submit - 1;
    }
  } else if (e.key === 'ArrowRight' && submits && current_submit < submits.length) {
    if (e.shiftKey) {
      target = submits.length;
    } else {
      target = current_submit + 1;
    }
  }
  if (target !== null) {
    document.location.href = `../${target}${document.location.hash}`;
  }
}

async function load() {
  const res = await fetch(url);
  const json = await res.json();
  current_submit = json['current_submit'];
  deadline = json['deadline'];
  submits = json['submits'];
  files = json['sources'].map((source) => new SourceFile(source));
  summaryComments = json['summary_comments'];

  // Hide all files by default if there is more than one file
  if (files.length > 1) {
    for (const file of files) {
      file.opened = false;
    }
  }

  // But if some file is selected, show that file
  const selectedFile = goToSelectedLines();
  if (selectedFile !== null) {
    for (const file of files) {
      if (file.source.path === selectedFile) {
        file.opened = true;
      }
    }
  }
}

function countComments(comments) {
  comments = comments || {};
  const counts = {
    user: 0,
    automated: 0
  };
  for (const line of Object.values(comments)) {
    for (const comment of Object.values(line)) {
      if (comment.type === 'automated') {
        counts.automated += 1;
      } else {
        counts.user += 1;
      }
    }
  }
  return counts;
}

$: allOpen = files && files.reduce((sum, file) => sum + file.opened, 0) === files.length;
async function toggleOpen() {
  files = files.map((file) => {
    file.opened = !allOpen;
    return file;
  });
}
load();

let selectedRows = null;

function goToSelectedLines() {
  const s = document.location.hash.split(';', 2);
  if (s.length == 2) {
    const parts = s[1].split(':');
    if (parts.length == 2) {
      const range = parts[1].split('-');

      selectedRows = {
        path: parts[0],
        from: parseInt(range[0]),
        to: parseInt(range[1] || range[0])
      };

      setTimeout(() => {
        const el = document.querySelector(
          `table[data-path="${CSS.escape(parts[0])}"] .linecode[data-line="${CSS.escape(selectedRows.from)}"]`
        );
        el.scrollIntoView();
      }, 0);

      return parts[0];
    }
  }
  return null;
}

window.addEventListener('hashchange', goToSelectedLines);
</script>

<svelte:window on:keydown={keydown} />

{#if files === null}
  <div class="d-flex justify-content-center">
    <SyncLoader />
  </div>
{:else}
  <div class="float-end">
    {#if files.length > 1}
      <button class="btn btn-link p-0" on:click={toggleOpen} title="Expand or collapse all files">
        {#if allOpen}
          <span><span class="iconify" data-icon="ant-design:folder-open-filled"></span></span>
        {:else}
          <span><span class="iconify" data-icon="ant-design:folder-filled"></span></span>
        {/if}
      </button>
    {/if}

    <button class="btn p-0 btn-link" title={commentsUI.title} on:click={changeCommentState}>
      <!-- because iconify-icon web component is not used in kelvin, this destroys everything in the div component if the icon changes
      it doesn't work without it because the span gets translated to svg and the key block ignores that -->
      {#key commentsUI.icon}
        <div><span class="iconify" data-icon={commentsUI.icon}></span></div>
      {/key}
    </button>
    <button
      class="btn p-0 btn-link"
      title="Diff vs previous version(s)"
      on:click={() => (showDiff = !showDiff)}
      ><span class="iconify" data-icon="fa-solid:history"></span></button>
    <a href="kelvin:{document.location.href.split('#')[0]}download" title="Open on your PC"
      ><span class="iconify" data-icon="fa-solid:external-link-alt"></span></a>
    <a href="download" download title="Download"
      ><span class="iconify" data-icon="fa-solid:download"></span></a>
  </div>

  {#if showDiff}
    <SubmitsDiff {submits} {current_submit} {deadline} />
  {/if}

  <SummaryComments
    {summaryComments}
    on:saveComment={(evt) => saveComment(evt.detail)}
    on:setNotification={setNotification} />

  {#each files as file}
    <h2 class="file-header">
      <span on:click={() => (file.opened = !file.opened)}>
        <span title="Toggle file visibility">{file.source.path}</span>
        {#if file.source.comments && Object.keys(file.source.comments).length}
          {@const comments = countComments(file.source.comments)}
          {#if comments.user > 0}
            <span
              class="badge bg-secondary"
              title="Student/teacher comments"
              style="font-size: 60%;">{comments.user}</span>
          {/if}
          {#if comments.automated > 0}
            <span class="badge bg-primary" title="Automation comments" style="font-size: 60%;"
              >{comments.automated}</span>
          {/if}
        {/if}
      </span>{#if file.source.type == 'source' && file.source.content}<CopyToClipboard
          content={() => file.source.content}
          title="Copy the source code to the clipboard"
          ><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"
          ></span
          ></CopyToClipboard
        >{/if}
    </h2>
    {#if file.opened}
      {#if file.source.error}
        <span class="text-muted">{file.source.error}</span>
      {:else if file.source.type == 'source'}
        {#if file.source.content_url}
          Content too large, show <a href={file.source.content_url}>raw content</a>.
        {:else}
          <SubmitSource
            path={file.source.path}
            code={file.source.content}
            comments={file.source.comments}
            selectedRows={selectedRows && selectedRows.path === file.source.path
              ? selectedRows
              : null}
            on:setNotification={setNotification}
            on:saveComment={(evt) => saveComment({ ...evt.detail, source: file.source.path })} />
        {/if}
      {:else if file.source.type === 'img'}
        <img src={file.source.src} />
      {:else if file.source.type === 'video'}
        <video controls>
          {#each file.source.sources as src}
            <source {src} />
          {/each}
        </video>
      {:else}The preview cannot be shown.{/if}
    {/if}
  {/each}
{/if}

<style>
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
