<script>
  import {onDestroy} from 'svelte';
  import CodeMirror from 'codemirror';
  import 'codemirror/lib/codemirror.css';
  import 'codemirror/mode/clike/clike.js';
  import 'codemirror/mode/yaml/yaml.js';
  import 'codemirror/mode/markdown/markdown.js';
  import 'codemirror/addon/display/fullscreen.js';
  import 'codemirror/addon/display/fullscreen.css';

  export let value;
  export let filename;
  export let autofocus = false;
  export let disabled = false;
  export let extraKeys = {};

  function toMode(filename) {
    const parts = filename.split('.');
    const ext = parts[parts.length - 1].toLowerCase();
    const map = {
      'c': 'text/x-csrc',
      'h': 'text/x-csrc',
      'cpp': 'text/x-c++src',
      'md': 'markdown',
      'yml': 'yaml',
      'yaml': 'yaml',
    };
    return map[ext];
  }

  let editor, editorEl;
  $: if(editorEl && !editor) {
      editor = CodeMirror.fromTextArea(editorEl, {
        mode: toMode(filename),
        autofocus,
        readOnly: disabled,
        extraKeys: {
          "F11": function(cm) {
            cm.setOption("fullScreen", !cm.getOption("fullScreen"));
          },
          "Esc": function(cm) {
            if(cm.getOption("fullScreen")) {
                cm.setOption("fullScreen", false);
            }
          },
          ...extraKeys,
        }
      });

      editor.on('change', doc => {
        value = doc.getValue();
      });

      let timer;
      let observer = new MutationObserver(muts => {
          if(timer) {
            clearInterval(timer);
          }
          timer = setTimeout(() => editor.refresh(), 100);
      });
      observer.observe(
        document.querySelector('.CodeMirror'),
        {attributes: true}
      );
  }

  $: if(editor && editor.getValue() != value) {
    editor.setValue(value);
  }

  $: if(editor) {
    editor.setOption('mode', toMode(filename));
  }

  $: if(editor) {
    editor.setOption('readOnly', disabled);
  }

  onDestroy(() => {
    if(editor) {
      editor.toTextArea();
    }
  });
</script>
<style>
:global(.CodeMirror) {
  border: 1px solid #ced4da;
  border-radius: .25rem;
  resize: vertical;
}
</style>

<textarea class="form-control" bind:this={editorEl} bind:value={value}></textarea>
