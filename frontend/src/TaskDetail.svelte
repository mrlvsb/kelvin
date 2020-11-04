<script>
  import { onMount } from "svelte";
  import SubmitSource from "./SubmitSource.svelte";
  import SyncLoader from "./SyncLoader.svelte";
  import CopyToClipboard from './CopyToClipboard.svelte'
  import {fetch} from './api.js'

  export let url;
  let sources = null;

  async function saveComment(evt) {
    if(evt.detail.id === undefined) {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: evt.detail.text,
          source: evt.detail.source,
          line: evt.detail.line,
        })
      });

      const json = await res.json();

      sources = sources.map(source => {
        if(source.path === evt.detail.source) {
          (source.comments[evt.detail.line - 1] = source.comments[evt.detail.line - 1] || []).push(json);
        }
        return source;
      });
    } else {
      const res = await fetch(url, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: evt.detail.id,
          text: evt.detail.text,
        })
      });

      sources = sources.map(source => {
        if(evt.detail.text == '') {
          source.comments = Object.fromEntries(Object.entries(source.comments).map(([lineNum, comments]) => {
            return [lineNum, comments.filter(comment => comment.id !== evt.detail.id)];
          }));
        } else {
          source.comments = Object.fromEntries(Object.entries(source.comments).map(([lineNum, comments]) => {
            return [lineNum, comments.map(comment => {
              if(comment.id === evt.detail.id) {
                  comment.text = evt.detail.text;
              }
              return comment;
            })];
          }));
        }
        return source;
      });
    }
    
    if(evt.detail.success) {
      evt.detail.success();
    }
  }

  async function load() {
    const res = await fetch(url);
    sources = (await res.json())['sources'];
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
  {#each sources as source}
    <h2>
      {source.path}{#if source.type == 'source'}<CopyToClipboard content={() => source.content} title='Copy the source code to the clipboard'><span class="iconify" data-icon="clarity:copy-to-clipboard-line" style="height: 20px"></span></CopyToClipboard>{/if}
    </h2>
    {#if source.type == 'source'}
      <SubmitSource
        code={source.content}
        comments={source.comments}
        on:saveComment={(evt) => {evt.detail.source = source.path; saveComment(evt)}} />
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
