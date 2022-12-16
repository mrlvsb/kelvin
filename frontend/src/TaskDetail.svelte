<svelte:window on:keydown={keydown} />

<script>
  import SubmitSource from "./SubmitSource.svelte";
  import SyncLoader from "./SyncLoader.svelte";
  import CopyToClipboard from './CopyToClipboard.svelte'
  import SummaryComments from './SummaryComments.svelte'
  import SubmitsDiff from './SubmitsDiff.svelte'
  import {fetch} from './api.js'
  import { user } from "./global"
  import { notifications } from './notifications.js'

  export let url;
  let files = null;
  let summaryComments = [];
  let submits = null;
  let current_submit = null;
  let deadline = null;
  let showDiff = false;
  let showComments = true;

  class SourceFile {
      constructor(source) {
          this.source = source;
          this.opened = true;
      }
  }

  function updateCommentProps(id, newProps) {
    function update(items) {
      return items.map(c => {
        if(c.id == id) {
          if(newProps === null) {
            return null;
          }
          return {...c, ...newProps};
        }
        return c;
      }).filter(c => c !== null);
    }

    files = files.map(file => {
      if(file.source.comments) {
        file.source.comments = Object.fromEntries(Object.entries(file.source.comments).map(([lineNum, comments]) => {
          return [lineNum, update(comments)];
        }));
      }
      return file;
    });

    summaryComments = update(summaryComments);
  }

  async function addNewComment(comment) {
    const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(comment)
    });

    const json = await res.json();
    if(!comment.source) {
      summaryComments = [
        ...await Promise.all(summaryComments.map(markCommentAsRead)),
        json
      ];
    } else {
      files = await Promise.all(files.map(async file => {
        if(file.source.path === comment.source) {
          let comments = await Promise.all((file.source.comments[comment.line - 1] || []).map(markCommentAsRead));
          file.source.comments[comment.line - 1] = [...comments, json];
        }
        return file;
      }));
    }
  }

  async function updateComment(id, text) {
    const res = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id: id,
        text: text,
      })
    });

    updateCommentProps(id, text === '' ? null : {text});
  }

  async function saveComment(comment) {
    if(comment.id) {
      await updateComment(comment.id, comment.text);
    } else {
      await addNewComment(comment);
    }
    if(comment.success) {
      comment.success();
    }
  }

  async function markCommentAsRead(comment) {
    if(comment.unread && comment.author_id !== $user.id && comment.notification_id) {
      await notifications.markRead(comment.notification_id);
      comment.unread = false;
    }
    return comment;
  }

  async function setNotification(evt) {
    async function walk(comments) {
      if(comments.filter(c => c.id === evt.detail.comment_id).length) {
        for(const comment of comments) {
          if(comment.unread && comment.author_id !== $user.id && comment.notification_id) {
            await notifications.markRead(comment.notification_id);
            updateCommentProps(comment.id, {unread: evt.detail.unread});
          }
        }
      }
    }

    await walk(summaryComments);
    for(const source of files) {
      if(source.source.comments) {
        for(const comments of Object.values(source.source.comments)) {
          await walk(comments);
        }
      }
    }
  }

  function keydown(e) {
    if(e.target.getAttribute('contenteditable') || e.target.tagName === 'TEXTAREA' || e.target.tagName == 'INPUT') {
      return;
    }

    if(e.key === "ArrowLeft" && current_submit > 1) {
      document.location.href = `../${current_submit-1}${document.location.hash}`;
    } else if(e.key === "ArrowRight" && submits && current_submit < submits.length) {
      document.location.href = `../${current_submit+1}${document.location.hash}`;
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

    goToSelectedLines();
  }

  function countComments(comments) {
      comments = comments || {};
      return Object.values(comments).reduce((sum, line) => sum + line.length, 0);
  }

  $: allOpen = files && files.reduce((sum, file) => sum + file.opened, 0) === files.length;
  async function toggleOpen() {
    files = files.map(file => {
        file.opened = !allOpen
        return file;
    });
  }
  load();

  let selectedRows = null;

  function goToSelectedLines() {
    const s = document.location.hash.split(';', 2);
    if(s.length == 2) {
      const parts = s[1].split(':');
      if(parts.length == 2) {
        const range = parts[1].split('-');

        selectedRows = {
          path: parts[0],
          from: parseInt(range[0]),
          to: parseInt(range[1] || range[0]),
        };

        setTimeout(() => {
          const el = document.querySelector(`table[data-path="${CSS.escape(parts[0])}"] .linecode[data-line="${CSS.escape(selectedRows.from)}"]`);
          el.scrollIntoView();
        }, 0);
      }
    }
  }

  window.addEventListener('hashchange', goToSelectedLines);  
</script>

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
</style>

{#if files === null}
  <div class="d-flex justify-content-center">
    <SyncLoader />
  </div>
{:else}
  <div class="float-right" >
    {#if files.length > 1}
      <button class="btn btn-link p-0" on:click={toggleOpen} title="Expand or collapse all files">
        {#if allOpen}
          <span><span class="iconify" data-icon="ant-design:folder-open-filled"></span></span>
        {:else}
          <span><span class="iconify" data-icon="ant-design:folder-filled"></span></span>
        {/if}
      </button>
    {/if}

    <button class="btn p-0 btn-link" title="Toggle comments" on:click={() => showComments = !showComments}><span class="iconify" data-icon="fa-solid:comment"></span></button>
    <button class="btn p-0 btn-link" title="Diff vs previous version(s)" on:click={() => showDiff = !showDiff}><span class="iconify" data-icon="fa-solid:history"></span></button>
    <a href="kelvin:{document.location.href.split('#')[0]}download" title="Open on your PC"><span class="iconify" data-icon="fa-solid:external-link-alt"></span></a>
    <a href="download" download title="Download"><span class="iconify" data-icon="fa-solid:download"></span></a>
  </div>

  {#if showDiff}
    <SubmitsDiff {submits} {current_submit} {deadline} />
  {/if}

  <SummaryComments {summaryComments} on:saveComment={evt => saveComment(evt.detail)} on:setNotification={setNotification} />

  {#each files as file}
    <h2 class="file-header" title="Toggle file visibility">
      <span on:click={() => file.opened = !file.opened}>
      {file.source.path}
      {#if file.source.comments && Object.keys(file.source.comments).length}
        <span class="badge badge-dark" style="font-size: 60%;">{countComments(file.source.comments)}</span>
      {/if}
      </span>{#if file.source.type == 'source' && file.source.content}<CopyToClipboard content={() => file.source.content} title='Copy the source code to the clipboard'><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"></span></CopyToClipboard>{/if}
    </h2>
    {#if file.opened}
      {#if file.source.error}
        <span class="text-muted">{file.source.error}</span>
      {:else if file.source.type == 'source' }
        {#if file.source.content_url }
          Content too large, show <a href="{ file.source.content_url }">raw content</a>.
        {:else}
          <SubmitSource
          path={file.source.path}
          code={file.source.content}
          comments={showComments ? file.source.comments : []}
          selectedRows={selectedRows && selectedRows.path === file.source.path ? selectedRows : null}
          on:setNotification={setNotification}
          on:saveComment={evt => saveComment({...evt.detail, source: file.source.path})} />
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
