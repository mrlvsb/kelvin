<script>
    import { createEventDispatcher } from 'svelte'
    import hljs from 'highlight.js';
    import 'highlight.js/styles/github.css';
    import CodeRow from './CodeRow.svelte'

    export let code;
    export let comments;
    
    let addingCommentToLine = -1;

    const dispatch = createEventDispatcher();

    $: highlightedLines = hljs.highlightAuto(code)['value'].split('\n');
</script>

<table>
    {#each highlightedLines as line, lineNumber}
        <CodeRow
            lineNumber={lineNumber + 1}
            {line}
            comments={comments[lineNumber]}
            showAddingForm={addingCommentToLine === lineNumber + 1}
            on:showCommentForm={evt => addingCommentToLine = evt.detail}
            on:saveComment
          />
    {/each}
</table>

