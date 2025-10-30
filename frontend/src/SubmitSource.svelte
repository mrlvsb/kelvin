<script>
import { createEventDispatcher } from 'svelte';
import CodeRow from './CodeRow.svelte';
import hljs from 'highlight.js/lib/core';
export let code;
export let comments;
export let selectedRows = -1;
export let path;

let addingCommentToLine = -1;
let highlightedLines = [];

const dispatch = createEventDispatcher();

/* To fixt warning in JS console
// In SubmitSource.svelte, when highlighting code:
// Instead of:
element.innerHTML = hljs.highlightAuto(code).value;

// Use:
const highlighted = hljs.highlight(code, { language: 'auto', ignoreIllegals: true });
element.innerHTML = highlighted.value;

// Or better yet, escape first:
import { escape } from 'html-escaper'; // or use a similar utility
const escaped = escape(code);
const highlighted = hljs.highlight(escaped, { language: 'auto' });
element.innerHTML = highlighted.value;
*/

$: {
  const container = document.createElement('div');
  container.innerHTML = hljs.highlightAuto(code)['value'];

  // fix multiline comments
  container.querySelectorAll('.hljs-comment').forEach((el) => {
    if (el.innerText.indexOf('\n') >= 0) {
      let prev = el;
      for (const line of el.innerText.split('\n')) {
        const e = document.createElement('span');
        e.classList.add('hljs-comment');
        e.innerText = line;
        el.parentNode.insertBefore(e, prev.nextSibling);
        prev = el.parentNode.insertBefore(document.createTextNode('\n'), e.nextSibling);
      }
      el.remove();
    }
  });

  highlightedLines = container.innerHTML.split('\n');
}

let selecting = 0;
let userSelected = false;

function update(to) {
  let from = selecting;
  if (from > to) {
    [from, to] = [to, from];
  }

  document.location.hash = `#src;${path}:${from}${to != from ? '-' + to : ''}`;
}

function mousedown(e) {
  if (e.target.tagName == 'SPAN') {
    return;
  }
  userSelected = true;
  const td = e.target.closest('tr td:first-of-type');
  if (td) {
    selecting = td.closest('tr').rowIndex + 1;
    update(selecting);
  }
}

function mouseover(e) {
  const td = e.target.closest('tr td:first-of-type');
  if (td && selecting >= 1) {
    update(td.closest('tr').rowIndex + 1);
  }
}
</script>

<table
  on:mousedown={mousedown}
  on:mouseover={mouseover}
  on:mouseup={() => (selecting = 0)}
  data-path={path}>
  {#each highlightedLines as line, lineNumber}
    <CodeRow
      lineNumber={lineNumber + 1}
      {line}
      comments={comments[lineNumber]}
      showAddingForm={addingCommentToLine === lineNumber + 1}
      selected={selectedRows &&
        lineNumber + 1 >= selectedRows.from &&
        lineNumber + 1 <= selectedRows.to}
      scroll={selectedRows && userSelected == 0 && lineNumber + 1 == selectedRows.from}
      on:showCommentForm={(evt) => (addingCommentToLine = evt.detail)}
      on:setNotification
      on:resolveSuggestion
      on:saveComment />
  {/each}
</table>
