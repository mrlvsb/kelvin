<script>
  import { createEventDispatcher } from "svelte";
  import CodeRow from "./CodeRow.svelte";
  import hljs from "highlight.js/lib/core";

  export let code;
  export let comments;

  let addingCommentToLine = -1;
  let highlightedLines = [];

  const dispatch = createEventDispatcher();

  $: {
    const container = document.createElement("div");
    container.innerHTML = hljs.highlightAuto(code)["value"];

    // fix multiline comments
    container.querySelectorAll(".hljs-comment").forEach(el => {
      if (el.innerText.indexOf("\n") >= 0) {
        let prev = el;
        for (const line of el.innerText.split("\n")) {
          const e = document.createElement("span");
          e.classList.add("hljs-comment");
          e.innerText = line;
          el.parentNode.insertBefore(e, prev.nextSibling);
          prev = el.parentNode.insertBefore(
            document.createTextNode("\n"),
            e.nextSibling
          );
        }
        el.remove();
      }
    });

    highlightedLines = container.innerHTML.split("\n");
  }
</script>

<table>
  {#each highlightedLines as line, lineNumber}
    <CodeRow
      lineNumber={lineNumber + 1}
      {line}
      comments={comments[lineNumber]}
      showAddingForm={addingCommentToLine === lineNumber + 1}
      on:showCommentForm={(evt) => (addingCommentToLine = evt.detail)}
      on:setNotification
      on:saveComment />
  {/each}
</table>
