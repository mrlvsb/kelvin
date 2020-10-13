<script>
  import CodeMirror from 'codemirror';
  import 'codemirror/lib/codemirror.css';
  import 'codemirror/mode/clike/clike.js';
  import 'codemirror/mode/yaml/yaml.js';
  import 'codemirror/mode/markdown/markdown.js';

  export let value;
  export let filename;

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
      });

      editor.on('change', doc => {
        value = doc.getValue();
      });
  }

  $: if(editor && editor.getValue() != value) {
    editor.setValue(value);
  }

  $: if(editor) {
    editor.setOption('mode', toMode(filename));
  }
</script>
<style>
:global(.CodeMirror) {
  border: 1px solid #ced4da;
  border-top: 0;
  border-radius: .25rem;
}
</style>

<textarea class="form-control" rows=20 bind:this={editorEl} bind:value={value}></textarea>
