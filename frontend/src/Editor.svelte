<script>
  import {onDestroy} from 'svelte';
  import CodeMirror from 'codemirror';
  import {lintPipeline} from './PipelineValidation.js'
  import {curTheme} from "./utils.js"
  import 'codemirror/lib/codemirror.css'
  import 'codemirror/mode/clike/clike.js';
  import 'codemirror/mode/yaml/yaml.js';
  import 'codemirror/mode/python/python.js';
  import 'codemirror/mode/markdown/markdown.js';
  import 'codemirror/mode/htmlmixed/htmlmixed.js';
  import 'codemirror/addon/display/fullscreen.js';
  import 'codemirror/addon/display/fullscreen.css';
  import 'codemirror/addon/lint/lint.js'
  import 'codemirror/addon/lint/lint.css'
  import 'codemirror/addon/hint/show-hint.js'
  import 'codemirror/addon/hint/show-hint.css'

  export let value;
  export let filename = '';
  export let autofocus = false;
  export let disabled = false;
  export let extraKeys = {};
  export let wrap = false;

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
      'py': 'python',
      'htm': 'htmlmixed',
      'html': 'htmlmixed',
    };
    return map[ext];
  }
  
  function getTheme(value) {
    return value == "dark" ? "dracula" : "default";
  }

  let editor, editorEl;
  $: if(editorEl && !editor) {
      editor = CodeMirror.fromTextArea(editorEl, {
        mode: toMode(filename),
        autofocus,
        lineWrapping: wrap,
        gutter: false,
        gutters: ["CodeMirror-lint-markers"],
        spellcheck: true,
        theme: getTheme($curTheme),
        inputStyle: "contenteditable",
        readOnly: disabled,
        tabSize: 2,
        extraKeys: {
          "Ctrl-Space": "autocomplete",
          "F11": function(cm) {
            cm.setOption("fullScreen", !cm.getOption("fullScreen"));
          },
          "Esc": function(cm) {
            if(cm.getOption("fullScreen")) {
                cm.setOption("fullScreen", false);
            }
          },
          "Tab": function(cm) {
            cm.execCommand("insertSoftTab");
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
    editor.setOption('readOnly', disabled);

    editor.setOption('gutters', filename == '/config.yml' ? ["CodeMirror-lint-markers"] : [])
    editor.setOption('gutter', filename == '/config.yml')
    editor.setOption('lint', filename == '/config.yml' ? lintPipeline : null)
    editor.setOption('spellcheck', filename != '/config.yml')
    editor.setOption('filename', filename);
    editor.setOption("theme", getTheme($curTheme));
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
  
  :global(.disabled > .CodeMirror) {
    background: #eee;
  }
  
  :global(.disabled > .CodeMirror .CodeMirror-cursors) {
    display: none;
  }
  </style>

<div class:disabled={disabled}>
  <textarea class="form-control" bind:this={editorEl} bind:value={value}></textarea>
</div>
