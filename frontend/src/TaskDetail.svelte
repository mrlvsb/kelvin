<script>
  import SubmitSource from "./SubmitSource.svelte";
  import SyncLoader from "./SyncLoader.svelte";
  import CopyToClipboard from './CopyToClipboard.svelte'
  import {fetch} from './api.js'
  import SummaryComments from './SummaryComments.svelte'

  export let url;
  let sources = null;
  let summaryComments = [];

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
      summaryComments = [...summaryComments, json];
    } else {
      sources = sources.map(source => {
        if(source.path === comment.source) {
          (source.comments[comment.line - 1] = source.comments[comment.line - 1] || []).push(json);
        }
        return source;
      });
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

    function update(items) {
      return items.map(c => {
        if(c.id === id) {
          if(text === '') {
            return null;
          }
          c.text = text;
        }
        return c;
      }).filter(c => c !== null);
    }

    sources = sources.map(source => {
      source.comments = Object.fromEntries(Object.entries(source.comments).map(([lineNum, comments]) => {
        return [lineNum, update(comments)];
      }));
      return source;
    });

    summaryComments = update(summaryComments);
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

  async function load() {
    const res = await fetch(url);
    const json = await res.json();
    sources = json['sources'];
    summaryComments = json['summary_comments'];
  }
  load();
</script>

<style>
  video,
  img {
    max-width: 100%;
  }
</style>

{#if sources === null}
  <div class="d-flex justify-content-center">
    <SyncLoader />
  </div>
{:else}
  <SummaryComments {summaryComments} on:saveComment={evt => saveComment(evt.detail)}/>

  {#each sources as source}
    <h2>
      {source.path}{#if source.type == 'source'}<CopyToClipboard content={() => source.content} title='Copy the source code to the clipboard'><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"></span></CopyToClipboard>{/if}
    </h2>
    {#if source.type == 'source'}
      <SubmitSource
        code={source.content}
        comments={source.comments}
        on:saveComment={evt => saveComment({...evt.detail, source: source.path})} />
    {:else if source.type === 'img'}
      <img src={source.src} />
    {:else if source.type === 'video'}
      <video controls>
        {#each source.sources as src}
          <source {src} />
        {/each}
      </video>
    {:else}The preview cannot be shown.{/if}
  {/each}
{/if}
