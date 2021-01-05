<script>
  import SubmitSource from "./SubmitSource.svelte";
  import SyncLoader from "./SyncLoader.svelte";
  import CopyToClipboard from './CopyToClipboard.svelte'
  import {fetch} from './api.js'
  import SummaryComments from './SummaryComments.svelte'
  import { user } from "./global";
  import { notifications } from './notifications.js'

  export let url;
  let files = null;
  let summaryComments = [];

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
      if(source.comments) {
        for(const comments of Object.values(source.comments)) {
          await walk(comments);
        }
      }
    }
  }

  async function load() {
    const res = await fetch(url);
    const json = await res.json();
    files = json['sources'].map((source) => new SourceFile(source));
    summaryComments = json['summary_comments'];
  }

  $: allOpen = files && files.reduce((sum, file) => sum + file.opened, 0) === files.length;
  async function toggleOpen() {
    files = files.map(file => {
        file.opened = !allOpen
        return file;
    });
  }
  load();
</script>

<style>
  video,
  img {
    max-width: 100%;
  }
  .file-header {
      cursor: pointer;
  }
  .file-header:hover {
      text-decoration: underline;
  }
</style>

{#if files === null}
  <div class="d-flex justify-content-center">
    <SyncLoader />
  </div>
{:else}
  <SummaryComments {summaryComments} on:saveComment={evt => saveComment(evt.detail)} on:setNotification={setNotification} />

  {#if files.length > 1}
  <div>
    <button class="btn p-0 ml-auto d-block" on:click={toggleOpen}>
      {#if allOpen}
        <span><span class="iconify" data-icon="ant-design:folder-open-filled"></span></span>
      {:else}
        <span><span class="iconify" data-icon="ant-design:folder-filled"></span></span>
      {/if}
    </button>
  </div>
  {/if}

  {#each files as file}
    <h2 class="file-header" title="Toggle file visibility" on:click={() => file.opened = !file.opened}>
      {file.source.path}{#if file.source.type == 'source'}<CopyToClipboard content={() => file.source.content} title='Copy the source code to the clipboard'><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"></span></CopyToClipboard>{/if}
    </h2>
    {#if file.opened }
      {#if file.source.type == 'source' }
        {#if file.source.content_url }
          Content too large, show <a href="{ file.source.content_url }">raw content</a>.
        {:else}
          <SubmitSource
          code={file.source.content}
          comments={file.source.comments}
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
